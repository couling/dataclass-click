import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from dataclass_click import option


@dataclass
class LoggingConfig:
    enable_debug_logging: Annotated[bool, option("--debug", is_flag=True, help="Enable Debug logging")]
    log_file: Annotated[
        Path | None,
        option(type=click.Path(dir_okay=False, file_okay=True, path_type=Path), help="Log file, default stderr")
    ]


def configure_logging(config: LoggingConfig) -> None:
    args = {}
    args["level"] = logging.DEBUG if config.enable_debug_logging else logging.INFO
    if config.log_file is not None:
        args["filename"] = config.log_file
    logging.basicConfig(**args)