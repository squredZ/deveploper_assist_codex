from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
import re

from pydantic import BaseModel, Field, field_validator, model_validator

Severity = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
MatchType = Literal["substring", "regex"]


def validate_relative_path(value: str) -> str:
    if not value:
        raise ValueError("path must not be empty")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError("path must be relative")
    if ".." in path.parts:
        raise ValueError("path must not contain '..'")
    if "\\" in value:
        raise ValueError("path must use '/' separators")
    return value


def validate_time_string(value: str) -> str:
    datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return value


class SourceRef(BaseModel):
    file: str
    line: int | None = Field(default=None, ge=1)
    symbol: str | None = None

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        return validate_relative_path(value)


class RegexValidated(BaseModel):
    pattern: str
    match_type: MatchType = "substring"

    @model_validator(mode="after")
    def validate_regex_pattern(self):
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
        return self
