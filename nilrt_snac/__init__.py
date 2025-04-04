"""nilrt-snac."""

import logging
import pathlib
from enum import IntEnum

__version__ = "2.0.0"

SNAC_DATA_DIR = pathlib.Path(__file__).resolve().parents[3] / "share" / "nilrt-snac"

logger = logging.getLogger(__package__)
logger.addHandler(logging.NullHandler())


class Errors(IntEnum):  # noqa: D101 - Missing docstring in public class (auto-generated noqa)
    EX_OK = 0
    EX_ERROR = 1
    EX_USAGE = 2
    EX_BAD_ENVIRONMENT = 128
    EX_CHECK_FAILURE = 129


class SNACError(Exception):  # noqa: D101 - Missing docstring in public class (auto-generated noqa)
    def __init__(  # noqa: D107 - Missing docstring in __init__ (auto-generated noqa)
        self, message, return_code=Errors.EX_ERROR
    ):
        super().__init__(message)
        self.return_code = return_code
