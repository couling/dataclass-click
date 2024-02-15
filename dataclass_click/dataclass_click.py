__all__ = [
    "option",
    "argument",
    "dataclass_click",
    "DontPassType",
    "DONT_PASS",
    "register_type_inference",
]

import dataclasses
import functools
import operator
import types
import typing
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, overload, Concatenate
from uuid import UUID

import click.core

Param = typing.ParamSpec("Param")
RetType = typing.TypeVar("RetType")
Arg = typing.TypeVar("Arg")
_T = typing.TypeVar("_T")

InferenceType = dict[typing.Type[Any], click.ParamType]

_TYPE_INFERENCE: InferenceType = {
    int: click.INT,
    str: click.STRING,
    float: click.FLOAT,
    bool: click.BOOL,
    UUID: click.UUID,
    datetime: click.DateTime(),
    Path: click.Path(path_type=Path),
}


@dataclasses.dataclass
class _DelayedCall(typing.Generic[Param, RetType]):
    """Delayed call to a click decorator

    The idea of this is that the arguments for a click decorator are collected but can then be mutated before actually
    calling it."""
    callable: Callable[Param, RetType]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclasses.dataclass
class _DelayedFunction(typing.Generic[Param, RetType]):
    callable: Callable[Param, RetType]

    def __call__(self, *args: Param.args, **kwargs: Param.kwargs) -> _DelayedCall[Param, RetType]:
        return _DelayedCall(self.callable, args, kwargs)


class DontPassType(Enum):
    """Type hint for DONT_PASS"""
    DONT_PASS = None


DONT_PASS = DontPassType.DONT_PASS
"""Set a default to this and dataclass_click will not pass the value as a kwarg to the dataclass constructor.

This allows using the dataclass own default value instead of a click default."""


@overload
def dataclass_click(
    arg_class: typing.Type[Arg],
    *,
    type_inferences: InferenceType | None = None,
    factory: Callable[..., Arg] | None = None
) -> Callable[[Callable[Concatenate[Arg, Param], RetType]], Callable[..., RetType]]:
    ...


@overload
def dataclass_click(
        arg_class: typing.Type[Arg],
        *,
        kw_name: str | None,
        type_inferences: InferenceType | None = None,
        factory: Callable[..., Arg] | None = None) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    ...


def dataclass_click(arg_class, *, kw_name=None, type_inferences=None, factory=None):
    """Decorator to add options and arguments, collecting the results into a dataclass object instead of many kwargs

    arg_class can be any class type as long as annotations can be extracted with inspect.  Either the arg_class
    constructor must accept kwarg arguments to match annotated field names (default for a @dataclass), or a factory
    function (callable object) must be passed that accepts those kwargs and returns an object of arg_class.

    Note that newer annotation types such as PEP 655 ``Required[]`` and ``NotRequired[]`` annotations not
    well-supported: ``Annotated`` must be the outermost annotation and other such annotations like ``Required`` and
    ``NotRequired`` will prevent dataclass-click from inferring data types.

    Eg:
    ```python
    @dataclass
    class Config:
        foo: Annotated[int, dataclass_click.argument()]
        bar: Annotated[int, dataclass_click.option()]
        baz: Annotated[int, dataclass_click.option("--bob")]

    @click.command
    @dataclass_click.dataclass_click(Config):
    def main(config: Config):
        ...
    ```

    :param arg_class: The class object to pass
    :param kw_name: If set, pass the dataclass object by to this kwarg name instead of the first positional argument
    :param type_inferences: Type inference overrides.  It is preferred register type inferences globally if possible.
    :param factory: A factory function to use instead of the constructor"""

    def decorator(func) -> Callable[..., RetType]:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            arg_class_args = {}
            for key in annotations:
                # DONT_PASS is also used by calling code to indicate defaults that should not be passed
                value = kwargs.pop(key, DONT_PASS)
                if value is not DONT_PASS:
                    arg_class_args[key] = value

            arg_class_object = factory_(**arg_class_args)  # type: ignore
            if kw_name is not None:
                kwargs[kw_name] = arg_class_object
            else:
                args = (arg_class_object, *args)
            return func(*args, **kwargs)

        for annotation in annotations.values():
            delayed_decorator = annotation.callable(*annotation.args, **annotation.kwargs)
            wrapper = delayed_decorator(wrapper)

        return wrapper

    factory_ = factory if factory is not None else arg_class
    annotations = _collect_click_annotations(arg_class)
    _patch_names(annotations)
    _patch_click_types(arg_class, annotations, type_inferences)
    _patch_required(arg_class, annotations)
    return decorator


def _patch_names(annotations: dict[str, _DelayedCall]) -> None:
    """Set names for all options and arguments

    Two things may be added:
     - The attribute name will always be added, allowing the user input to be mapped back onto the dataclass
     - For options, an option name may be added if there are none.  Eg: some_option will add --some-option

    :param annotations: Annotations to mutate
    :return: None annotations are mutated in place"""
    for key, annotation in annotations.items():
        if annotation.callable is click.option and not any(name.startswith("") for name in annotation.args):
            annotation.args = (_option_name(key), *annotation.args)
        annotation.args = (key, *annotation.args)


def _patch_click_types(
        arg_class: typing.Type[Arg], annotations: dict[str, _DelayedCall], inferences: InferenceType | None) -> None:
    """Default option and argument types based on their dataclass type hint

    :param arg_class: The dataclass to collect
    :param annotations: The annotations that have already been collected
    :param inferences: Optional dict of type hint inferences that override the defaults.
    :return: None, annotations are changed in place
    """
    if inferences is not None:
        complete_type_inferences = _TYPE_INFERENCE.copy()
        complete_type_inferences.update(inferences)
    else:
        complete_type_inferences = _TYPE_INFERENCE

    type_hints = typing.get_type_hints(arg_class)
    for key, annotation in annotations.items():
        hint: typing.Type[Any]
        _, hint = _strip_optional(type_hints[key])
        if "type" not in annotation.kwargs:
            stub: click.core.Option | click.core.Argument
            if annotation.callable is click.option:
                stub = click.core.Option(annotation.args, **annotation.kwargs)
                if stub.is_flag:
                    continue
            else:
                stub = click.core.Argument(annotation.args, **annotation.kwargs)
            annotation.kwargs["type"] = _eval_type(key, hint, stub, complete_type_inferences)


def _eval_type(
        key: str, hint: typing.Type[Any], stub: click.core.Option | click.core.Argument,
        inferences: InferenceType) -> click.ParamType | tuple[click.ParamType, ...]:
    try:
        hint_origin = typing.get_origin(hint)
        hint_args = typing.get_args(hint)
        if stub.multiple or stub.nargs == -1:
            if hint_origin is tuple and len(hint_args) == 2 and hint_args[1] is ...:
                hint = hint_args[0]
                hint_origin = typing.get_origin(hint)
                hint_args = typing.get_args(hint)
            else:
                raise TypeError(f"Could not infer ParamType for {key} type {hint!r}. Explicitly annotate type=<type>")
        if stub.nargs > 1:
            if hint_origin is tuple:
                return tuple(inferences[hint_arg] for hint_arg in hint_args)
        else:
            return inferences[hint]
    except (KeyError, IndexError):
        pass
    raise TypeError(f"Could not infer ParamType for {key} type {hint!r}. Explicitly annotate type=<type>")


def _patch_required(arg_class: typing.Type[Arg], annotations: dict[str, _DelayedCall]) -> None:
    """Default click option to required if typehint is not OPTIONAL

    If a type hint on the dataclass was not Optional and neither ``default` nor ``required`` were set, then mark the
    option as ``required=True``.
    :param arg_class: The dataclass being analyzed
    :param annotations: Annotations that have already been analyzed
    :return: None, annotations are updated in place"""
    type_hints = typing.get_type_hints(arg_class)
    for key, annotation in annotations.items():
        hint: typing.Type[Any]
        is_optional, hint = _strip_optional(type_hints[key])
        if not is_optional:
            if annotation.callable is click.option:
                # If required or default set directly.
                if "required" not in annotation.kwargs and "default" not in annotation.kwargs:
                    # Stub uses click's parser rather than trying to second guess how click will behave
                    # If click would imply is_flag or multiple
                    stub = click.core.Option(annotation.args, **annotation.kwargs)
                    if not stub.is_flag and not stub.multiple:
                        annotation.kwargs["required"] = True


def _strip_optional(attribute_type: typing.Type[_T]) -> tuple[bool, typing.Type[_T]]:
    """Strip NoneType out of union type

    We need to know the type for inference purposes, but NoneType is handled separately, inferring something is optional
    or required. This function removes NoneType from any union and, if that leaves a union of one thing, strips off the
    union entirely.:
    :param attribute_type: The type hint of the attribute
    :return: The type hint minus any union with NoneType.  This may or may not be a union."""
    if typing.get_origin(attribute_type) is types.UnionType:
        args = typing.get_args(attribute_type)
        if types.NoneType in typing.get_args(attribute_type):
            args = tuple(arg for arg in args if arg != types.NoneType)
            if len(args) == 1:
                return True, args[0]
            return True, functools.reduce(operator.or_, args)
    return False, attribute_type


def _collect_click_annotations(arg_class: typing.Type[Arg]) -> dict[str, _DelayedCall]:
    """Find all dataclass_click annotations on a class object

    Technically there's no reason this must be a dataclass, but that's the general assumption.
    This assumes there are no exotic forms of annotation such as Required, or that they will magically be flattened out.
    https://github.com/python/cpython/issues/113702
    Annotation arguments are flattened out to only include _DelayedCall objects.  If more than one _DelayedCall object
    exists, only the first will be taken.

    :param arg_class: Dataclass to analyze
    :return: A dictionary _DelayedCall keyed by attribute names"""
    annotations: dict[str, _DelayedCall] = {}
    for key, value in typing.get_type_hints(arg_class, include_extras=True).items():
        if typing.get_origin(value) is typing.Annotated:
            for annotation in typing.get_args(value):
                if isinstance(annotation, _DelayedCall):
                    annotations[key] = annotation
                    break
    return {
        key: dataclasses.replace(annotation, kwargs=annotation.kwargs.copy())
        for key, annotation in annotations.items()
    }


def _option_name(attribute_name: str) -> str:
    """Infer option name from attribute name"""
    return "--" + attribute_name.lower().replace("_", "-")


def register_type_inference(
        python_type: typing.Type[Any],
        click_param_type: click.ParamType | None,
        *,
        override_okay: bool = False) -> None:
    """Register a type inference globally

    Pass ``click_param_type=None`` to de-register a type.  This can even be done for in-built custom types so use with
    caution!

    This allows custom click ParameterType objects to be inferred directly from dataclass type hints.

    Unions are supported but note that unions containing None/NoneType (OPTIONAL) are not and will raise a
    NotImplementedError. That's because OPTIONAL is stripped from the type hint to default options to ``required=True``
    :param python_type: The python type which may be seen as a type hint on a dataclass
    :param click_param_type: The click ``ParamType`` to infer from the type hint.  If None, the inference will be
        de-registered
    :param override_okay: If False (default) raise a ``ValueError`` if the python_type is already registered.
        If attempting to de-register an inference with ``click_param_type=None`` this must be set to True.
    """
    if not override_okay and python_type in _TYPE_INFERENCE:
        raise ValueError(
            f"Refusing to modify inference for {python_type!r} without override_okay=True. "
            f"Existing inference: {click_param_type!r}")
    is_optional, _ = _strip_optional(python_type)
    if is_optional:
        raise NotImplementedError(f"Optional python types are not supported.  Got {python_type!r}")
    if click_param_type is None:
        _TYPE_INFERENCE.pop(python_type, None)
    else:
        _TYPE_INFERENCE[python_type] = click_param_type


option = _DelayedFunction(click.option)
"""Annotation to add to a dataclass attribute indicating a click option.

Arguments are almost identical to click.option(), but do not include a name to give to the python argument"""

argument = _DelayedFunction(click.argument)
"""Annotation to add to a dataclass attribute indicating a click argument.

These will be added to the resulting decorator in the order the attribute appears on the dataclass

Arguments are almost identical to click.option(), but do not include a name to give to the python argument"""
