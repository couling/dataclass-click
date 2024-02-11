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
import inspect
import types
import typing
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import click

Param = typing.ParamSpec("Param")
RetType = typing.TypeVar("RetType")
Arg = typing.TypeVar("Arg")


@dataclasses.dataclass
class _DelayedCall(typing.Generic[Param, RetType]):
    callable: Callable[Param, RetType]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclasses.dataclass
class _DelayedFunction(typing.Generic[Param, RetType]):
    callable: Callable[Param, RetType]

    def __call__(self, *args: Param.args, **kwargs: Param.kwargs) -> _DelayedCall[Param, RetType]:
        return _DelayedCall(self.callable, args, kwargs)


class DontPassType(Enum):
    DONT_PASS=None


DONT_PASS = DontPassType.DONT_PASS
"""Set a default to this and dataclass_click will not pass the value as a kwarg to the dataclass constructor.

This allows using the dataclass own default value instead of a click default."""


def dataclass_click(
    arg_class: typing.Type[Arg],
    *,
    kw_name: str | None = None,
    type_inferences: dict[Any, click.ParamType] | None = None
) -> Callable[[Callable[[Arg], RetType]], Callable[..., RetType]]:

    def decorator(func) -> Callable[..., RetType]:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            arg_class_args = {}
            for key in annotations:
                # DONT_PASS is also used by calling code to indicate defaults that should not be passed
                value = kwargs.pop(key, DONT_PASS)
                if value is not DONT_PASS:
                    arg_class_args[key] = value
            arg_class_object = arg_class(**arg_class_args)
            if kw_name is not None:
                kwargs[kw_name] = arg_class_object
            else:
                args = (arg_class_object, *args)
            return func(*args, **kwargs)

        for annotation in annotations.values():
            delayed_decorator = annotation.callable(*annotation.args, **annotation.kwargs)
            wrapper = delayed_decorator(wrapper)

        return wrapper

    annotations = _collect_click_annotations(arg_class)
    _patch_names(annotations)
    _patch_click_types(arg_class, annotations, type_inferences)
    return decorator


def _patch_names(annotations: dict[str,_DelayedCall]) -> None:
    for key, annotation in annotations.items():
        if annotation.callable is click.option and not any(name.startswith("") for name in annotation.args):
            annotation.args = (_option_name(key), *annotation.args)
        annotation.args = (key, *annotation.args)


def _patch_click_types(arg_class: typing.Type[Arg], annotations: dict[str,_DelayedCall], inferences) -> None:
    if inferences is not None:
        complete_type_inferences = _TYPE_INFERENCE.copy()
        complete_type_inferences.update(inferences)
    else:
        complete_type_inferences = _TYPE_INFERENCE

    missing_types = [key for key, value in annotations.items() if "type" not in value.kwargs]

    if missing_types:
        type_hints = typing.get_type_hints(arg_class)
        for key in missing_types:
            hint = type_hints.get(key, None)
            if hint is not None:
                if hint is not None and typing.get_origin(hint) is types.UnionType:
                    args = typing.get_args(hint)
                    if len(args) != 2:
                        continue
                    if args[0] is types.NoneType:
                        hint = args[1]
                    elif args[1] is types.NoneType:
                        hint = args[0]
                if hint in complete_type_inferences:
                    annotations[key].kwargs["type"] = complete_type_inferences[hint]
                    continue
                raise TypeError(f"Could not infer ParamType for {key} type {hint!r}. Explicitly annotate type=<type>")


def _collect_click_annotations(arg_class: typing.Type[Arg]) -> dict[str,_DelayedCall]:
    annotations: dict[str, _DelayedCall] = {}
    for key, value in inspect.get_annotations(arg_class).items():
        if typing.get_origin(value) is typing.Annotated:
            for annotation in typing.get_args(value):
                if isinstance(annotation, _DelayedCall):
                    annotations[key] = annotation
                    break
    return annotations


def _option_name(attribute_name: str) -> str:
    return "--" + attribute_name.lower().replace("_", "-")


_TYPE_INFERENCE = {
    int: click.INT,
    str: click.STRING,
    float: click.FLOAT,
    bool: click.BOOL,
    UUID: click.UUID,
    datetime: click.DateTime(),
    Path: click.Path(path_type=Path),
}


def register_type_inference(python_type: Any, click_param_type: click.ParamType | None) -> None:
    if click_param_type is None:
        _TYPE_INFERENCE.pop(python_type, None)
    else:
        _TYPE_INFERENCE[python_type] = click_param_type


option = _DelayedFunction(click.option)
argument = _DelayedFunction(click.argument)
