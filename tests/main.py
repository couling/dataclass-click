import logging

import click
from dataclass_click import dataclass_click

from tests.logging_configuration import LoggingConfig, configure_logging


logger = logging.getLogger(__name__)


@click.group()
@click.argument("SOME_ARGUMENT")
@dataclass_click(LoggingConfig, kw_name="logging_config")
def main(logging_config: LoggingConfig, some_argument: str):
    configure_logging(logging_config)
    logger.debug("Starting up")
    logger.info("%s", some_argument)

if __name__ == '__main__':
    main()