from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hilog_agent.schemas.common import (
    MatchType,
    Severity,
    validate_relative_path,
    validate_time_string,
)


class FeatureModuleIndex(BaseModel):
    name: str
    yaml_path: str
    responsibility: str

    @model_validator(mode="after")
    def validate_yaml_path(self):
        validate_relative_path(self.yaml_path)
        expected = f"modules/{self.name}.yaml"
        if self.yaml_path != expected:
            raise ValueError(f"yaml_path must be {expected}")
        return self


class FeatureEntrypoint(BaseModel):
    name: str
    module: str
    file: str | None = None
    symbol: str | None = None
    description: str

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str | None) -> str | None:
        return validate_relative_path(value) if value is not None else value


class ExpectedLog(BaseModel):
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


class CallChainStep(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    id: str
    module: str
    file: str | None = None
    symbol: str | None = None
    description: str
    optional: bool
    async_: bool = Field(alias="async")
    expected_logs: list[ExpectedLog]

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str | None) -> str | None:
        return validate_relative_path(value) if value is not None else value


class CallChain(BaseModel):
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    steps: list[CallChainStep]


class FailureKeyLog(BaseModel):
    tag: str
    level: str | None = None
    pattern: str
    match_type: MatchType = "substring"
    severity: Severity
    confidence_weight: float
    related_step: str | None = None
    suggested_cause: str
    meaning: str

    @model_validator(mode="after")
    def validate_regex(self):
        if self.match_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex pattern: {exc}") from exc
        return self


class FailurePattern(BaseModel):
    symptom: str
    related_steps: list[str]
    key_logs: list[FailureKeyLog]
    possible_causes: list[str]


class FeatureMetadata(BaseModel):
    status: Literal["draft", "active"]
    owner: str | None = None
    version: int = Field(ge=1)
    updated_at: str
    review_notes: list[str]

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: str) -> str:
        return validate_time_string(value)


class FeatureYaml(BaseModel):
    name: str
    display_name: str
    description: str
    keywords: list[str]
    modules: list[FeatureModuleIndex]
    entrypoints: list[FeatureEntrypoint] = Field(default_factory=list)
    call_chains: list[CallChain]
    failure_patterns: list[FailurePattern]
    metadata: FeatureMetadata
    extensions: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self):
        module_names = {module.name for module in self.modules}
        if self.metadata.status == "active":
            if not self.keywords:
                raise ValueError("active feature requires keywords")
            if not self.call_chains:
                raise ValueError("active feature requires call_chains")
            if not self.failure_patterns:
                raise ValueError("active feature requires failure_patterns")

        for entrypoint in self.entrypoints:
            if entrypoint.module not in module_names:
                raise ValueError(f"entrypoint references unknown module {entrypoint.module}")

        step_ids: set[str] = set()
        for chain in self.call_chains:
            if self.metadata.status == "active" and not chain.steps:
                raise ValueError("active feature call_chain requires steps")
            for step in chain.steps:
                if step.module not in module_names:
                    raise ValueError(f"step {step.id} references unknown module {step.module}")
                if step.id in step_ids:
                    raise ValueError(f"duplicate step id {step.id}")
                step_ids.add(step.id)

        for pattern in self.failure_patterns:
            for step_id in pattern.related_steps:
                if step_id not in step_ids:
                    raise ValueError(f"failure pattern references unknown step {step_id}")
            for key_log in pattern.key_logs:
                if key_log.related_step and key_log.related_step not in step_ids:
                    raise ValueError(f"key log references unknown step {key_log.related_step}")
        return self
