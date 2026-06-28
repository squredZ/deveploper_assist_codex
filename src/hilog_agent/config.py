from pathlib import Path
import logging
from typing import Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AnalysisConfig(BaseModel):
    default_window_seconds: int = 60
    min_feature_score: int = 5
    feature_score_margin: int = 3
    max_log_events_for_llm: int = 200
    max_code_snippets_for_llm: int = 20


class OutputConfig(BaseModel):
    format: Literal["text", "json"] = "text"
    verbose: bool = False
    include_evidence: bool = True
    include_raw_log_lines: bool = False
    include_generated_yaml: bool = False


class AddModuleConfig(BaseModel):
    backup: bool = False


class ReasoningConfig(BaseModel):
    effort: str = "medium"
    summary: str = "auto"


class LlmConfig(BaseModel):
    enabled: bool = True
    provider: Literal["openai_compatible"] = "openai_compatible"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"
    timeout_seconds: int = 120
    max_output_tokens: int = 4000
    structured_output: Literal["json_schema", "json_object", "prompt_only"] = (
        "json_schema"
    )
    max_validation_retries: int = 3
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)


class OrchestratorConfig(BaseModel):
    mode: Literal["bounded_react"] = "bounded_react"
    max_tool_calls: int = 8
    max_llm_rounds: int = 4
    tool_timeout_seconds: int = 30
    allowed_tools: list[str] = Field(
        default_factory=lambda: [
            "read_feature",
            "list_features",
            "filter_hilog_by_time",
            "match_logs_by_patterns",
            "read_file",
            "search_code",
        ]
    )


class PromptConfig(BaseModel):
    module_generation: Path = Path("prompts/module_generation.md")
    feature_update: Path = Path("prompts/feature_update.md")


class AgentConfig(BaseModel):
    repo_root: Path = Path(".")
    features_dir: Path = Path("features")
    log_temp_dir: Path = Path(".tmp/hilog-agent")
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    add_module: AddModuleConfig = Field(default_factory=AddModuleConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    prompts: PromptConfig = Field(default_factory=PromptConfig)


def load_config(path: Path) -> AgentConfig:
    if not path.exists():
        logger.info("config file not found; using defaults path=%s", path)
        return AgentConfig()
    logger.info("loading config file path=%s", path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = AgentConfig.model_validate(data)
    logger.info(
        "loaded config features_dir=%s repo_root=%s llm_provider=%s",
        config.features_dir,
        config.repo_root,
        config.llm.provider,
    )
    if config.llm.api_key:
        logger.warning("config contains plaintext llm.api_key; prefer api_key_env")
    return config


def redact_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
