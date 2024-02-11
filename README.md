# dataclass-click

Make structuring your click arguments simple!

Click is pretty simple to start with, but when your programs get complex with command groups and large numbers of shared
arguments, you find yourself repeating a lot of work.

The idea of `dataclass-click` is to move the `@option` and `@argument` decorators off into annotations on dataclasses 
and pass dataclass objects instead of kwargs.

## Simple Example

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from dataclass_click import argument, dataclass_click, option


@dataclass
class Config:
    target: Annotated[Path, argument()]  # Auto-inferred type for built-in click types
    foo: Annotated[float, option(required=True)]  # Auto-inferrd option names if you want them
    bar: Annotated[int | None, option("--other")]  # You can use pretty much any click option you are used to


@click.command()
@dataclass_click(Config)
def main(config: Config):
    # All your args neatly packaged.
    print(config.target, config.foo, config.bar)
    print(list(config.target.iterdir())) 
```

## Use Cases

It's for complex programs!  For simple programs you may not see the point of this.  That's fine, Click is great!

Where you need dataclass-click is with complex programs; particularly when using command groups.  Inevitably 
you want to start sharing arguments (eg a `--debug` option) between many commands in a group and quickly find yourself
replicating a lot of code.

### Separation of Concerns

What dataclass-click offers you is to keep **configuration** and **feature** close together but neatly seperate a 
**feature** from a **command**.

It's easier if I show you.  Let's take "logging" as the feature we're interested in:

`logging_configuration.py`

```python
import click
from typing import Annotated
from dataclass_click import option
from dataclasses import dataclass
from pathlib import Path
import logging


@dataclass
class LoggingConfig:
    enable_debug_logging: Annotated[bool, option("--debug", is_flag=True, help="Enable Debug logging")]
    log_file: Annotated[Path | None, option(type=click.Path(path_type=Path), help="Log file, default stderr")]


def configure_logging(config: LoggingConfig) -> None:
    args = {}
    args["level"] = logging.DEBUG if config.enable_debug_logging else logging.INFO
    if config.log_file is not None:
        args["filename"] = config.log_file
    logging.basicConfig(**args)
```

`main.py`

```python
import logging

import click
from dataclass_click import dataclass_click

from .logging_configuration import LoggingConfig, configure_logging


logger = logging.getLogger(__name__)


@click.group()
@click.argument("SOME_ARGUMENT")
@dataclass_click(LoggingConfig, kw_name="logging_config")
def main(logging_config: LoggingConfig, some_argument: str):
    configure_logging(logging_config)
    logger.debug("Starting up")
    logger.info("%s", some_argument)
```

Our main program doesn't know anything about logging at all or it's options.  That's now wholly self-contained in
the `logging_configuration` module!

And yet, if we take a look at the help text:

```
Usage: main.py [OPTIONS] SOME_ARGUMENT COMMAND [ARGS]...

Options:
  --log-file FILE  Log file, default stderr
  --debug          Enable Debug logging
  --help           Show this message and exit.
```

### Re-using options

The other big use case, especially for multi-command programs is re-using option definitions between commands.

With click on its own, you are tricked into an anti-pattern of putting shared options in a `group`.
This seems okay-ish, except your options end up going in odd places, and in the worst cases [it just doesn't work(#295)](https://github.com/pallets/click/issues/295#issuecomment-708129734)

```shell
my-command --db-url postgresq://localhost/ add-thing --thing=foo
```

Outside of click, in the rest of the unix world, that would have been:


```shell
my-command add-thing --db-url postgresq://localhost/ --thing=foo
```

dataclass-click let's you do just that:

```python
from dataclass_click import option, argument, dataclass_click
import click
from dataclasses import dataclass
from typing import Annotated

@dataclass
class DatabaseSettings:
    db_url: Annotated[str, option()]

    
@dataclass
class UserConnectionSettings:
    username: Annotated[str, option(prompt="Username?")]
    password: Annotated[str, option(prompt="Password?", hide_input=True)]


@dataclass
class ChangeThing(UserConnectionSettings):
    thing: Annotated[str, option(required=True)]


@click.group()
def main():
    pass


@main.command()
@dataclass_click(ChangeThing)
def add_thing(change_spec: ChangeThing):
    print(f"Adding {change_spec.thing}")


# Even if you don't have a username and password you can still get help text
# See click issue #295
@main.command()
@dataclass_click(ChangeThing)
def delete_thing(change_spec: ChangeThing):
    print(f"Deleting {delete_thing()}")


# This one doesn't need the user and password, so won't prompt for them!
@main.command()
@dataclass_click(DatabaseSettings, kw_name="db_settings")
@click.option("--interval", type=click.INT, required=True)
def ping_database(db_settings: DatabaseSettings, interval: int):
    print(f"Pinging database every {interval} seconds")

```