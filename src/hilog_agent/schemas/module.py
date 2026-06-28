from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hilog_agent.schemas.common import (
    Confidence,
    MatchType,
    Severity,
    SourceRef,
    validate_relative_path,
    validate_time_string,
)


class ModuleSymbol(BaseModel):
    name: str
    file: str
    kind: Literal["class", "function", "method", "interface", "enum", "config", "other"]
    relevance: Severity
    reason: str

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        return validate_relative_path(value)


class ModuleEntrypoint(BaseModel):
    name: str
    symbol: str
    file: str
    description: str
    trigger: str | None = None
    confidence: Confidence

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        return validate_relative_path(value)


class ModuleLog(BaseModel):
    tag: str
    level: str | None = None
    pattern: str
    match_type: MatchType = "substring"
    meaning: str
    evidence_type: str
    related_step: str | None = None
    severity: Severity
    confidence_weight: float | None = None
    source: SourceRef

    @model_validator(mode="after")
    def validate_regex(self):
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
        return self


class CandidateExpectedLog(BaseModel):
    tag: str
    level: str | None = None
    pattern: str
    match_type: MatchType = "substring"
    evidence_type: str
    required: bool
    weight: float
    missing_meaning: str | None = None

    @model_validator(mode="after")
    def validate_regex(self):
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
        return self


class CandidateStep(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    id: str
    description: str
    file: str | None = None
    symbol: str | None = None
    async_: bool = Field(alias="async")
    optional: bool
    confidence: Confidence
    reason: str
    expected_logs: list[CandidateExpectedLog]

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str | None) -> str | None:
        return validate_relative_path(value) if value is not None else value


class FailureSignal(BaseModel):
    tag: str
    level: str | None = None
    pattern: str
    match_type: MatchType = "substring"
    severity: Severity
    suggested_cause: str
    meaning: str
    related_step: str | None = None
    confidence_weight: float | None = None
    source: SourceRef

    @model_validator(mode="after")
    def validate_regex(self):
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
        return self


class ModuleDependency(BaseModel):
    name: str
    type: Literal["module", "service", "library", "config", "external", "other"]
    direction: Literal["input", "output", "bidirectional", "unknown"]
    reason: str
    source: SourceRef | None = None


class ModuleMetadata(BaseModel):
    generated_by: str
    generated_at: str
    review_notes: list[str]

    @field_validator("generated_by")
    @classmethod
    def validate_generated_by(cls, value: str) -> str:
        if not value:
            raise ValueError("generated_by must not be empty")
        return value

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: str) -> str:
        return validate_time_string(value)


class ModuleYaml(BaseModel):
    name: str
    display_name: str
    code_path: str
    responsibility: str
    symbols: list[ModuleSymbol]
    entrypoints: list[ModuleEntrypoint] = Field(default_factory=list)
    logs: list[ModuleLog]
    candidate_steps: list[CandidateStep]
    failure_signals: list[FailureSignal]
    dependencies: list[ModuleDependency] = Field(default_factory=list)
    metadata: ModuleMetadata
    extensions: dict = Field(default_factory=dict)

    @field_validator("code_path")
    @classmethod
    def validate_code_path(cls, value: str) -> str:
        return validate_relative_path(value)

    @model_validator(mode="after")
    def validate_related_steps(self):
        step_ids = {step.id for step in self.candidate_steps}
        if len(step_ids) != len(self.candidate_steps):
            raise ValueError("candidate step ids must be unique")
        for log in self.logs:
            if log.related_step and log.related_step not in step_ids:
                raise ValueError(f"log references unknown candidate step {log.related_step}")
        for signal in self.failure_signals:
            if signal.related_step and signal.related_step not in step_ids:
                raise ValueError(
                    f"failure signal references unknown candidate step {signal.related_step}"
                )
        return self
