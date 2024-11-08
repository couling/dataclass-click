"""
This module exists to run MyPy checks.

It must parse by python, there's unit test that imports it, and it gets checked by mypy, but it has no practical use.
"""
import decimal
from dataclasses import dataclass
from typing import Annotated

import click

from dataclass_click import register_type_inference, option, argument, dataclass_click


class CustomParameterType(click.ParamType):
    pass


def register_something() -> None:
    register_type_inference(decimal.Decimal, CustomParameterType())


@dataclass
class Config:
    foo: Annotated[int, argument()]
    bar: Annotated[str, argument(nargs=1)]
    baz: Annotated[str | None, option()]
    bob: Annotated[str | None, option("--bonno")]


class Config2:
    a: Annotated[int, option()]


@click.command()
@dataclass_click(Config)
def main_a(config: Config):
    ...


@click.command()
@dataclass_click(Config, kw_name="a")
@click.option("--b")
def main_b(b: str | None, a: Config):
    ...


@click.command()
@dataclass_click(Config, kw_name="a")
@dataclass_click(Config2, kw_name="b")
def main_c(a: Config, b: Config2):
    ...


@click.command()
@dataclass_click(Config)
@dataclass_click(Config2, kw_name="b")
def main_d(a: Config, b: Config2):
    ...


@click.command()
@dataclass_click(Config2, kw_name="b")
@dataclass_click(Config)
def main_e(a: Config, b: Config2):
    ...

@click.command()
@dataclass_click(Config2)
@dataclass_click(Config)
def main_f(a: Config, b: Config2):
    ...
