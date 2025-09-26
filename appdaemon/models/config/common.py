from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, PlainSerializer, ValidationError

from appdaemon.utils import parse_timedelta

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

BoolNum = Annotated[bool, BeforeValidator(lambda v: False if int(v) == 0 else True)]
TimeType = Annotated[timedelta, BeforeValidator(parse_timedelta), PlainSerializer(lambda td: td.total_seconds())]


def coerce_path(v: str | Path) -> Path:
    """Coerce a string or Path to a resolved Path."""
    match v:
        case str() as path_string:
            return Path(path_string)
        case Path() as path:
            return path
        case _:
            raise ValidationError(f"Invalid type for path: {v}")

def coerce_abs_path(v: str | Path) -> Path:
    """Coerce a string or Path to a resolved Path."""
    return coerce_path(v).absolute()


CoercedPath = Annotated[Path, BeforeValidator(coerce_abs_path)]
CoercedRelPath = Annotated[Path, BeforeValidator(coerce_path)]
LogPath = Annotated[Literal["STDOUT", "STDERR"], BeforeValidator(lambda s: s.upper())] | CoercedPath
