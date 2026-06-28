from typing import Literal

from pydantic import BaseModel, Field, model_validator

from hilog_agent.schemas.common import Severity


ConfidenceLabel = Literal["high", "medium", "low"]


class RelatedFeatureSuggestion(BaseModel):
    feature: str
    reason: str


class ModuleGenerationResult(BaseModel):
    module_yaml: str
    analysis_summary: list[str]
    warnings: list[str]


class FeatureUpdateResult(BaseModel):
    updated_feature_yaml: str
    change_summary: list[str]
    warnings: list[str]
    related_feature_suggestions: list[RelatedFeatureSuggestion]


class WrittenFile(BaseModel):
    path: str
    action: Literal["created", "updated", "backup_created"]


class AddModuleResult(BaseModel):
    command: Literal["add-module"] = "add-module"
    feature: str
    module: str
    written_files: list[WrittenFile]
    analysis_summary: list[str]
    change_summary: list[str]
    warnings: list[str]
    related_feature_suggestions: list[RelatedFeatureSuggestion]
    module_yaml: str | None = None
    updated_feature_yaml: str | None = None


class RawRef(BaseModel):
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    timestamp: str | None = None


class Evidence(BaseModel):
    id: str
    source: Literal["hilog", "feature_yaml", "module_yaml", "code", "user_input"]
    type: Literal[
        "expected_log_hit",
        "failure_log_hit",
        "missing_required_log",
        "code_reference",
        "feature_match",
        "chain_match",
    ]
    feature: str | None = None
    chain: str | None = None
    step: str | None = None
    severity: Severity | None = None
    confidence_delta: float = 0
    summary: str
    raw_ref: RawRef | None = None


class Conclusion(BaseModel):
    summary: str
    confidence: ConfidenceLabel
    score: float | None = None


class RootCause(BaseModel):
    title: str
    confidence: ConfidenceLabel
    score: float | None = None
    related_step: str | None = None
    supporting_evidence: list[str]
    gaps: list[str]
    next_actions: list[str]


class ChainStepStatus(BaseModel):
    step: str
    status: Literal[
        "normal",
        "abnormal",
        "suspected_abnormal",
        "not_entered",
        "not_observed",
        "unknown",
    ]
    evidence: list[str]
    summary: str


class AnalysisStats(BaseModel):
    total_lines: int = 0
    parsed_lines: int = 0
    unparsed_lines: int = 0
    events_in_window: int = 0
    matched_events: int = 0


class AnalysisResult(BaseModel):
    command: Literal["analyze-log"] = "analyze-log"
    feature: str
    chain: str | None = None
    question: str | None = None
    conclusion: Conclusion
    root_causes: list[RootCause]
    chain_status: list[ChainStepStatus]
    evidence: list[Evidence]
    stats: AnalysisStats
    supplemental_suggestions: list[str] = []
    warnings: list[str] = []

    @model_validator(mode="after")
    def validate_evidence_references(self):
        evidence_ids = set()
        for item in self.evidence:
            if item.id in evidence_ids:
                raise ValueError("duplicate evidence id")
            evidence_ids.add(item.id)
        for cause in self.root_causes:
            if cause.supporting_evidence and not set(cause.supporting_evidence) <= evidence_ids:
                raise ValueError("root cause references unknown evidence")
        for status in self.chain_status:
            if status.evidence and not set(status.evidence) <= evidence_ids:
                raise ValueError("chain status references unknown evidence")
        return self
