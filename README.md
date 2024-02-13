# dataclass-click

Structure your click arguments.

dataclass-click lets you move your user arguments from kwargs to dataclasses, keeping things self-contained.

Click is pretty simple to start with, but when your program gets complex, you find yourself repeating a lot of work.
This is particularly true if you have command groups with shared arguments.

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
    # Auto-inferred type for built-in click types
    target: Annotated[Path, argument()]  
    
    # Auto-inferred option names
    foo: Annotated[float, option(required=True)]
    
    # Automatically map mismatched names
    bar: Annotated[int | None, option("--other")]


@click.command()
@dataclass_click(Config)
def main(config: Config):
    # All args neatly packaged.
    print(config.target, config.foo, config.bar)
    print(list(config.target.iterdir())) 
```

## Inference Features

### Name inference

The pythonic name for options and attributes is copied from the dataclass attribute name.
Options can then be named whatever you want. If you don't specify an option name, it will be inferred for you:

```python
from dataclasses import dataclass
from dataclass_click import option, argument
from typing import Annotated

@dataclass
class Config:
    foo: Annotated[str, argument()]
    bar: Annotated[str, option()]
    baz: Annotated[str, option("--bonno")]
```

```
Usage: main.py [OPTIONS] FOO

Options:
  --bonno TEXT
  --bar TEXT
  --help        Show this message and exit.
```

### Type Inference (Extensible)

#### Out of the box...

data-class click can infer click parameter type (eg: `option(type=click.INT)`) from the attribute type.
These types are static so if, like `click.Path`, you need arguments, you can always specify the type yourself like 
normal.

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from dataclass_click import option


@dataclass
class Config:
    a: Annotated[str, option()]       # click.STRING
    b: Annotated[bool, option()]      # click.BOOL
    c: Annotated[int, option()]       # click.INT
    d: Annotated[float, option()]     # click.FLOAT
    e: Annotated[UUID, option()]      # click.UUID
    f: Annotated[datetime, option()]  # click.DateTime()
    g: Annotated[Path, option()]      # click.Path(path_type=Path)
```

#### Extending it...

Type inference is extensible so a program can add and even change the default click ParameterTypes associated with a 
Python data type.  Eg: if you want to add a `Decimal`:

```python
from decimal import Decimal

import click
import dataclass_click


class DecimalParameterType(click.ParamType):
    name = "integer"

    def convert(self, value, param, ctx):
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(value)
        except ValueError:
            self.fail(f"{value!r} is not a valid decimal number", param, ctx)


DECIMAL = DecimalParameterType()

# Extend type inference to add Decimal
dataclass_click.register_type_inference(Decimal, DECIMAL)
```


### Required Inference

To avoid tricky mismatches between required options and optional attributes, dataclass-click will infer a field is 
required if neither `default=` nor `required=` are explicitly set and the attribute type hint is not optional:

```python
from dataclasses import dataclass
from typing import Annotated

from dataclass_click import option

@dataclass
class Config:
    # Infer --foo is required because str is not optional
    foo: Annotated[str, option()]
    
    # Infer --bar is not required because str | None is optional
    bar: Annotated[str | None, option()]
    
    # No inference performed because required= is set.
    baz: Annotated[str | None, option(required=True)]
    
    # Infer not required because default= set.
    bob: Annotated[str, option(default="no")]
    
    # If you want to shoot yourself in the foot, you can!
    # Not inferred because required=False.  
    # Click will pass None even though the attribute is not optional
    bonno: Annotated[str, option(required=False)]  
```

```
Usage: main.py [OPTIONS]

Options:
  --bob TEXT
  --baz TEXT  [required]
  --bar TEXT
  --foo TEXT  [required]
  --bonno
  --help      Show this message and exit.
```
