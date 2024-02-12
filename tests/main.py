import click

from dataclass_click import option, argument, dataclass_click
from dataclasses import dataclass
from typing import Annotated

@dataclass
class Config:
    foo: Annotated[str, argument()]
    bar: Annotated[str, option()]
    baz: Annotated[str, option("--bonno")]


@click.command()
@dataclass_click(Config)
def main(config: Config):
    ...

if __name__ == "__main__":
    main()