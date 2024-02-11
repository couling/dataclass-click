from dataclasses import dataclass
from typing import Annotated

import click
from click.testing import CliRunner

from dataclass_click import dataclass_click, option


def quick_run(command, *args: str, expect_exit_code: int = 0) -> None:
    result = CliRunner().invoke(command, args)
    assert result.exit_code == expect_exit_code


def test_extra_args_are_passed_through():

    @dataclass
    class Config:
        foo: Annotated[str, option("--foo", type=click.STRING,)]

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
    assert results == [((Config(foo=example_value_for_inferrable_type),), {})]
    # Belt and braces, check we got the right type
    assert isinstance(results[0][0][0].foo, inferrable_type)


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
    assert results == [((Config(foo=10),), {})]


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
    assert results == [((Config(baz=10),), {})]