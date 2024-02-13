from dataclasses import dataclass
from typing import Annotated, Any
import io
import click
import pytest
from click.testing import CliRunner

from dataclass_click import dataclass_click, option


def quick_run(command, *args: str, expect_exit_code: int = 0) -> None:
    result = CliRunner().invoke(command, args, catch_exceptions=False)
    assert result.exit_code == expect_exit_code


def test_extra_args_are_passed_through():

    @dataclass
    class Config:
        foo: Annotated[str, option(
            "--foo",
            type=click.STRING,
        )]

    @click.command()
    @click.option("--bar")
    @dataclass_click(Config)
    @click.option("--baz")
    def main(*args, **kwargs):
        results.append((args, kwargs))

    results = []
    quick_run(main, "--foo", "a", "--bar", "b", "--baz", "c")
    assert results == [((Config(foo="a"), ), {"bar": "b", "baz": "c"})]


def test_types_can_be_inferred(inferrable_type, example_value_for_inferrable_type):

    @dataclass
    class Config:
        foo: Annotated[inferrable_type, option("--foo")]

    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        results.append((args, kwargs))

    results = []
    if hasattr(example_value_for_inferrable_type, "isoformat"):
        str_value = example_value_for_inferrable_type.isoformat()
    else:
        str_value = str(example_value_for_inferrable_type)
    quick_run(main, "--foo", str_value)
    assert results == [((Config(foo=example_value_for_inferrable_type), ), {})]
    # Belt and braces, check we got the right type
    assert isinstance(results[0][0][0].foo, inferrable_type)


@pytest.mark.parametrize("args", [{}, {"is_flag": False}], ids=["no_args", "is_flag_false"])
def test_type_inference_raises(args: dict[str, Any]):

    class UnknownClass:
        pass

    @dataclass
    class Config:
        foo: Annotated[UnknownClass, option(**args)]

    with pytest.raises(TypeError):

        @click.command()
        @dataclass_click(Config)
        def main(*args, **kwargs):
            pass


@pytest.mark.parametrize("args", [{"type": click.INT}, {"is_flag": True}], ids=["type", "is_flag_true"])
def test_types_not_inferred(args: dict[str, Any]):

    class UnknownClass:
        pass

    @dataclass
    class Config:
        foo: Annotated[UnknownClass, option(**args)]

    # Make sure no exception is raised.
    # See test_type_inference_raises() for the counter example
    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        pass


def test_inferred_option_name():
    """Test that the option name can be inferred from the attribute name"""

    @dataclass
    class Config:
        foo: Annotated[int, option(type=click.INT)]

    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        results.append((args, kwargs))

    results = []
    quick_run(main, "--foo", "10")
    assert results == [((Config(foo=10), ), {})]


def test_mapped_option_name():
    """Test that the option name does not need to match the attribute name"""

    @dataclass
    class Config:
        baz: Annotated[int, option("--foo", type=click.INT)]

    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        results.append((args, kwargs))

    results = []
    quick_run(main, "--foo", "10")
    assert results == [((Config(baz=10), ), {})]


@pytest.mark.parametrize(["args", "expect"], [
    ({}, 2),
    ({"required": True}, 2),
    ({"required": False}, 0),
    ({"default": 10}, 0),
    ({"default": 10, "required": False}, 0)
], ids=["neither", "required-true", "required-false", "default", "both"])
def test_inferred_required(args: dict[str, Any], expect: int):

    @dataclass
    class Config:
        imply_required: Annotated[int, option(**args)]

    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        pass

    quick_run(main, expect_exit_code=expect)


@pytest.mark.parametrize(["args", "expect"], [
    ({}, 0),
    ({"required": True}, 2),
    ({"required": False}, 0),
    ({"default": 10}, 0),
    ({"default": 10, "required": False}, 0)
], ids=["neither", "required-true", "required-false", "default", "both"])
def test_inferred_required(args: dict[str, Any], expect: int):

    @dataclass
    class Config:
        imply_required: Annotated[int | None, option(**args)]

    @click.command()
    @dataclass_click(Config)
    def main(*args, **kwargs):
        pass

    quick_run(main, expect_exit_code=expect)


def test_dataclass_can_be_used_twice():
    @dataclass
    class Config:
        imply_required: Annotated[int, option()]

    @click.command()
    @dataclass_click(Config)
    def main_1(*args, **kwargs):
        pass

    @click.command()
    @dataclass_click(Config)
    def main_2(*args, **kwargs):
        pass