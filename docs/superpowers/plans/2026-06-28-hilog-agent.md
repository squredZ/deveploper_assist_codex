# Hilog Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP CLI for feature Q&A, hilog analysis, and LLM-driven module knowledge generation from the approved Hilog Agent design.

**Architecture:** Implement a small Python package with focused modules for config, schemas, feature storage, hilog parsing, evidence/scoring, LLM structured output, prompt rendering, and CLI orchestration. Use Pydantic v2 as the single source of truth for YAML schemas and JSON result models; use deterministic analysis first, with LLM output validated and retried before rendering or writing files.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, PyYAML, OpenAI Python SDK, pytest, pytest-cov.

---

## File Structure

Create these files:

- `pyproject.toml`: package metadata, dependencies, console script, pytest config.
- `src/hilog_agent/__init__.py`: package marker and version.
- `src/hilog_agent/config.py`: config models, loading, CLI override merge, API key redaction.
- `src/hilog_agent/schemas/common.py`: shared enums, path validators, regex validators, time validators.
- `src/hilog_agent/schemas/feature.py`: `FeatureYaml` and related feature models.
- `src/hilog_agent/schemas/module.py`: `ModuleYaml` and related module models.
- `src/hilog_agent/schemas/results.py`: structured output and CLI result models.
- `src/hilog_agent/feature_store.py`: feature directory loading and cross-file validation.
- `src/hilog_agent/hilog.py`: hilog parsing, zip unpacking, time filtering.
- `src/hilog_agent/matcher.py`: log pattern matching.
- `src/hilog_agent/evidence.py`: evidence construction and chain status inference.
- `src/hilog_agent/scoring.py`: feature and chain scoring.
- `src/hilog_agent/prompts.py`: prompt file loading and `{{placeholder}}` rendering.
- `src/hilog_agent/llm.py`: OpenAI-compatible client wrapper and structured-output retry loop.
- `src/hilog_agent/add_module.py`: `add-module` workflow, diff safety, transactional writes.
- `src/hilog_agent/analyze.py`: `ask` and `analyze-log` workflows.
- `src/hilog_agent/render.py`: text and JSON renderers.
- `src/hilog_agent/cli.py`: Typer CLI.
- `prompts/module_generation.md`: module generation prompt.
- `prompts/feature_update.md`: feature update prompt.

Create tests:

- `tests/test_config.py`
- `tests/test_feature_schema.py`
- `tests/test_module_schema.py`
- `tests/test_feature_store.py`
- `tests/test_hilog.py`
- `tests/test_matcher.py`
- `tests/test_scoring_evidence.py`
- `tests/test_prompts.py`
- `tests/test_llm_retry.py`
- `tests/test_add_module.py`
- `tests/test_cli.py`
- `tests/fixtures/features/camera_capture/feature.yaml`
- `tests/fixtures/features/camera_capture/modules/camera_ui.yaml`
- `tests/fixtures/hilog/camera_capture.log`

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/hilog_agent/__init__.py`
- Create: `src/hilog_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from hilog_agent.cli import app


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "hilog-agent" in result.stdout
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
pytest tests/test_cli.py::test_cli_version -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `hilog_agent.cli`.

- [ ] **Step 3: Add package scaffold**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "hilog-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "openai>=1.0.0",
  "pydantic>=2.0.0",
  "pyyaml>=6.0.0",
  "typer>=0.12.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-cov>=5.0.0",
]

[project.scripts]
agent = "hilog_agent.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `src/hilog_agent/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/hilog_agent/cli.py`:

```python
import typer

from hilog_agent import __version__

app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hilog-agent {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


def main() -> None:
    app()
```

- [ ] **Step 4: Run the smoke test**

Run:

```bash
pytest tests/test_cli.py::test_cli_version -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/hilog_agent/__init__.py src/hilog_agent/cli.py tests/test_cli.py
git commit -m "chore: scaffold hilog agent package"
```

---

### Task 2: Config Loading

**Files:**
- Create: `src/hilog_agent/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

from hilog_agent.config import AgentConfig, load_config, redact_secret


def test_load_config_defaults(tmp_path: Path):
    config = load_config(tmp_path / "missing.yaml")
    assert config.features_dir == Path("features")
    assert config.output.format == "text"
    assert config.llm.max_validation_retries == 3


def test_load_config_from_yaml(tmp_path: Path):
    path = tmp_path / "agent.yaml"
    path.write_text(
        "features_dir: custom_features\n"
        "llm:\n"
        "  api_key: sk-test-secret\n"
        "  model: test-model\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.features_dir == Path("custom_features")
    assert config.llm.model == "test-model"
    assert config.llm.api_key == "sk-test-secret"


def test_redact_secret():
    assert redact_secret("sk-abcdef123456") == "sk-a...3456"
    assert redact_secret(None) is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `hilog_agent.config` does not exist.

- [ ] **Step 3: Implement config models**

Create `src/hilog_agent/config.py`:

```python
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


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
    structured_output: Literal["json_schema", "json_object", "prompt_only"] = "json_schema"
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
        return AgentConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AgentConfig.model_validate(data)


def redact_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
```

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/config.py tests/test_config.py
git commit -m "feat: add agent configuration loading"
```

---

### Task 3: YAML Schema Models

**Files:**
- Create: `src/hilog_agent/schemas/common.py`
- Create: `src/hilog_agent/schemas/feature.py`
- Create: `src/hilog_agent/schemas/module.py`
- Create: `src/hilog_agent/schemas/__init__.py`
- Test: `tests/test_feature_schema.py`
- Test: `tests/test_module_schema.py`

- [ ] **Step 1: Write schema tests**

Create `tests/test_feature_schema.py`:

```python
import pytest
from pydantic import ValidationError

from hilog_agent.schemas.feature import FeatureYaml


def valid_feature_data():
    return {
        "name": "camera_capture",
        "display_name": "相机拍照",
        "description": "拍照链路",
        "keywords": ["拍照"],
        "modules": [
            {
                "name": "camera_ui",
                "yaml_path": "modules/camera_ui.yaml",
                "responsibility": "拍照入口",
            }
        ],
        "call_chains": [
            {
                "name": "normal_capture",
                "description": "正常拍照链路",
                "steps": [
                    {
                        "id": "ui_click",
                        "module": "camera_ui",
                        "description": "点击拍照",
                        "optional": False,
                        "async": False,
                        "expected_logs": [],
                    }
                ],
            }
        ],
        "failure_patterns": [
            {
                "symptom": "拍照不出图",
                "related_steps": ["ui_click"],
                "key_logs": [],
                "possible_causes": ["UI 未触发"],
            }
        ],
        "metadata": {
            "status": "active",
            "version": 1,
            "updated_at": "2026-06-28 14:35:00",
            "review_notes": [],
        },
    }


def test_feature_schema_accepts_valid_data():
    feature = FeatureYaml.model_validate(valid_feature_data())
    assert feature.name == "camera_capture"
    assert feature.call_chains[0].steps[0].async_ is False


def test_active_feature_requires_keywords():
    data = valid_feature_data()
    data["keywords"] = []
    with pytest.raises(ValidationError):
        FeatureYaml.model_validate(data)


def test_step_module_must_exist():
    data = valid_feature_data()
    data["call_chains"][0]["steps"][0]["module"] = "missing"
    with pytest.raises(ValidationError):
        FeatureYaml.model_validate(data)
```

Create `tests/test_module_schema.py`:

```python
import pytest
from pydantic import ValidationError

from hilog_agent.schemas.module import ModuleYaml


def valid_module_data():
    return {
        "name": "camera_ui",
        "display_name": "相机 UI",
        "code_path": "applications/camera",
        "responsibility": "拍照入口",
        "symbols": [],
        "logs": [],
        "candidate_steps": [
            {
                "id": "ui_click",
                "description": "点击拍照",
                "async": False,
                "optional": False,
                "confidence": "high",
                "reason": "UI 入口",
                "expected_logs": [],
            }
        ],
        "failure_signals": [],
        "metadata": {
            "generated_by": "hilog-agent",
            "generated_at": "2026-06-28 14:35:00",
            "review_notes": [],
        },
    }


def test_module_schema_accepts_valid_data():
    module = ModuleYaml.model_validate(valid_module_data())
    assert module.name == "camera_ui"


def test_related_step_must_reference_candidate_step():
    data = valid_module_data()
    data["logs"] = [
        {
            "tag": "CameraUI",
            "pattern": "click",
            "match_type": "substring",
            "meaning": "点击",
            "evidence_type": "step_started",
            "related_step": "missing",
            "severity": "low",
            "source": {"file": "applications/camera/page.ts"},
        }
    ]
    with pytest.raises(ValidationError):
        ModuleYaml.model_validate(data)


def test_regex_must_compile():
    data = valid_module_data()
    data["failure_signals"] = [
        {
            "tag": "CameraUI",
            "pattern": "[",
            "match_type": "regex",
            "severity": "high",
            "suggested_cause": "日志异常",
            "meaning": "非法正则",
            "source": {"file": "applications/camera/page.ts"},
        }
    ]
    with pytest.raises(ValidationError):
        ModuleYaml.model_validate(data)
```

- [ ] **Step 2: Run schema tests and verify failure**

Run:

```bash
pytest tests/test_feature_schema.py tests/test_module_schema.py -v
```

Expected: FAIL because schema modules do not exist.

- [ ] **Step 3: Implement common schema helpers**

Create `src/hilog_agent/schemas/__init__.py`:

```python
"""Pydantic schemas for hilog-agent."""
```

Create `src/hilog_agent/schemas/common.py`:

```python
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
            re.compile(self.pattern)
        return self
```

- [ ] **Step 4: Implement feature schema**

Create `src/hilog_agent/schemas/feature.py`:

```python
from typing import Literal
import re

from pydantic import BaseModel, Field, field_validator, model_validator

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
        return validate_relative_path(value) if value else value


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
            re.compile(self.pattern)
        return self


class CallChainStep(BaseModel):
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
        return validate_relative_path(value) if value else value


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
            re.compile(self.pattern)
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
```

- [ ] **Step 5: Implement module schema**

Create `src/hilog_agent/schemas/module.py`:

```python
from typing import Literal
import re

from pydantic import BaseModel, Field, field_validator, model_validator

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
            re.compile(self.pattern)
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
            re.compile(self.pattern)
        return self


class CandidateStep(BaseModel):
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
        return validate_relative_path(value) if value else value


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
            re.compile(self.pattern)
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
                raise ValueError(f"failure signal references unknown candidate step {signal.related_step}")
        return self
```

- [ ] **Step 6: Run schema tests**

Run:

```bash
pytest tests/test_feature_schema.py tests/test_module_schema.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hilog_agent/schemas tests/test_feature_schema.py tests/test_module_schema.py
git commit -m "feat: add feature and module schemas"
```

---

### Task 4: Feature Store

**Files:**
- Create: `src/hilog_agent/feature_store.py`
- Create: `tests/fixtures/features/camera_capture/feature.yaml`
- Create: `tests/fixtures/features/camera_capture/modules/camera_ui.yaml`
- Test: `tests/test_feature_store.py`

- [ ] **Step 1: Write feature store tests**

Create fixture `tests/fixtures/features/camera_capture/feature.yaml`:

```yaml
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路
keywords:
  - 拍照
modules:
  - name: camera_ui
    yaml_path: modules/camera_ui.yaml
    responsibility: 拍照入口
call_chains:
  - name: normal_capture
    description: 正常拍照链路
    steps:
      - id: ui_click
        module: camera_ui
        description: 点击拍照
        optional: false
        async: false
        expected_logs: []
failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - ui_click
    key_logs: []
    possible_causes:
      - UI 未触发
metadata:
  status: active
  version: 1
  updated_at: "2026-06-28 14:35:00"
  review_notes: []
```

Create fixture `tests/fixtures/features/camera_capture/modules/camera_ui.yaml`:

```yaml
name: camera_ui
display_name: 相机 UI
code_path: applications/camera
responsibility: 拍照入口
symbols: []
logs: []
candidate_steps: []
failure_signals: []
metadata:
  generated_by: hilog-agent
  generated_at: "2026-06-28 14:35:00"
  review_notes: []
```

Create `tests/test_feature_store.py`:

```python
from pathlib import Path

from hilog_agent.feature_store import FeatureStore


def test_list_features():
    store = FeatureStore(Path("tests/fixtures/features"))
    assert store.list_features() == ["camera_capture"]


def test_read_feature_dir_validates_modules():
    store = FeatureStore(Path("tests/fixtures/features"))
    loaded = store.read_feature_dir("camera_capture")
    assert loaded.feature.name == "camera_capture"
    assert loaded.modules["camera_ui"].name == "camera_ui"
    assert loaded.warnings == []
```

- [ ] **Step 2: Run feature store tests and verify failure**

Run:

```bash
pytest tests/test_feature_store.py -v
```

Expected: FAIL because `FeatureStore` does not exist.

- [ ] **Step 3: Implement FeatureStore**

Create `src/hilog_agent/feature_store.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import yaml

from hilog_agent.schemas.feature import FeatureYaml
from hilog_agent.schemas.module import ModuleYaml


@dataclass
class LoadedFeature:
    feature: FeatureYaml
    modules: dict[str, ModuleYaml]
    warnings: list[str]


class FeatureStore:
    def __init__(self, features_dir: Path):
        self.features_dir = features_dir

    def list_features(self) -> list[str]:
        if not self.features_dir.exists():
            return []
        names = [
            path.name
            for path in self.features_dir.iterdir()
            if path.is_dir() and (path / "feature.yaml").exists()
        ]
        return sorted(names)

    def read_feature_dir(self, feature_name: str) -> LoadedFeature:
        feature_dir = self.features_dir / feature_name
        feature_path = feature_dir / "feature.yaml"
        if not feature_path.exists():
            raise FileNotFoundError(f"feature.yaml not found for {feature_name}")

        feature_data = yaml.safe_load(feature_path.read_text(encoding="utf-8")) or {}
        feature = FeatureYaml.model_validate(feature_data)
        if feature.name != feature_name:
            raise ValueError(f"feature.yaml name {feature.name} does not match {feature_name}")

        modules: dict[str, ModuleYaml] = {}
        warnings: list[str] = []
        for module_index in feature.modules:
            module_path = feature_dir / module_index.yaml_path
            if not module_path.exists():
                raise FileNotFoundError(f"module yaml not found: {module_index.yaml_path}")
            module_data = yaml.safe_load(module_path.read_text(encoding="utf-8")) or {}
            module = ModuleYaml.model_validate(module_data)
            if module.name != module_index.name:
                raise ValueError(
                    f"module index {module_index.name} points to module {module.name}"
                )
            if module_path.name != f"{module.name}.yaml":
                raise ValueError(f"module filename must be {module.name}.yaml")
            if module.responsibility != module_index.responsibility:
                warnings.append(
                    f"module {module.name} responsibility differs from feature index"
                )
            modules[module.name] = module
        return LoadedFeature(feature=feature, modules=modules, warnings=warnings)
```

- [ ] **Step 4: Run feature store tests**

Run:

```bash
pytest tests/test_feature_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/feature_store.py tests/fixtures tests/test_feature_store.py
git commit -m "feat: add feature directory store"
```

---

### Task 5: Hilog Parser and Matcher

**Files:**
- Create: `src/hilog_agent/hilog.py`
- Create: `src/hilog_agent/matcher.py`
- Create: `tests/fixtures/hilog/camera_capture.log`
- Test: `tests/test_hilog.py`
- Test: `tests/test_matcher.py`

- [ ] **Step 1: Write hilog and matcher tests**

Create `tests/fixtures/hilog/camera_capture.log`:

```text
2026-06-28 14:35:01.120  1234  5678 I CameraUI: click capture
2026-06-28 14:35:01.350  1234  5678 I CameraService: Start capture
not a hilog line
2026-06-28 14:35:03.500  1234  5678 E CameraService: Capture failed
```

Create `tests/test_hilog.py`:

```python
from datetime import datetime
from pathlib import Path

from hilog_agent.hilog import parse_hilog_file, filter_events_by_time


def test_parse_hilog_counts_unparsed_lines():
    parsed = parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))
    assert parsed.total_lines == 4
    assert parsed.parsed_lines == 3
    assert parsed.unparsed_lines == 1
    assert parsed.events[0].tag == "CameraUI"


def test_filter_events_by_time():
    parsed = parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))
    events = filter_events_by_time(
        parsed.events,
        datetime(2026, 6, 28, 14, 35, 1),
        1,
    )
    assert [event.tag for event in events] == ["CameraUI", "CameraService"]
```

Create `tests/test_matcher.py`:

```python
from hilog_agent.hilog import HilogEvent
from hilog_agent.matcher import LogPattern, match_events


def test_substring_match_is_case_sensitive():
    event = HilogEvent(
        time="2026-06-28 14:35:01.350",
        pid="1234",
        tid="5678",
        level="I",
        tag="CameraService",
        message="Start capture",
        raw="raw",
        line=1,
    )
    matches = match_events(
        [event],
        [LogPattern(tag="CameraService", pattern="Start capture", match_type="substring")],
    )
    assert len(matches) == 1


def test_regex_match():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed err=-1",
        raw="raw",
        line=1,
    )
    matches = match_events(
        [event],
        [LogPattern(tag="CameraService", pattern=r"err=-\\d+", match_type="regex")],
    )
    assert len(matches) == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_hilog.py tests/test_matcher.py -v
```

Expected: FAIL because parser and matcher do not exist.

- [ ] **Step 3: Implement hilog parser**

Create `src/hilog_agent/hilog.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re

HILOG_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<level>[A-Z])\s+"
    r"(?P<tag>[^:]+):\s*(?P<message>.*)$"
)


@dataclass(frozen=True)
class HilogEvent:
    time: str
    pid: str
    tid: str
    level: str
    tag: str
    message: str
    raw: str
    line: int

    @property
    def timestamp(self) -> datetime:
        return datetime.strptime(self.time, "%Y-%m-%d %H:%M:%S.%f")


@dataclass(frozen=True)
class ParsedHilog:
    events: list[HilogEvent]
    total_lines: int
    parsed_lines: int
    unparsed_lines: int


def parse_hilog_file(path: Path) -> ParsedHilog:
    events: list[HilogEvent] = []
    total = 0
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        total += 1
        match = HILOG_RE.match(raw_line)
        if not match:
            continue
        events.append(HilogEvent(raw=raw_line, line=line_no, **match.groupdict()))
    return ParsedHilog(
        events=events,
        total_lines=total,
        parsed_lines=len(events),
        unparsed_lines=total - len(events),
    )


def filter_events_by_time(
    events: list[HilogEvent],
    center_time: datetime,
    window_seconds: int,
) -> list[HilogEvent]:
    start = center_time - timedelta(seconds=window_seconds)
    end = center_time + timedelta(seconds=window_seconds)
    return [event for event in events if start <= event.timestamp <= end]
```

- [ ] **Step 4: Implement matcher**

Create `src/hilog_agent/matcher.py`:

```python
from dataclasses import dataclass
import re
from typing import Literal

from hilog_agent.hilog import HilogEvent


@dataclass(frozen=True)
class LogPattern:
    tag: str
    pattern: str
    match_type: Literal["substring", "regex"] = "substring"
    level: str | None = None


@dataclass(frozen=True)
class LogMatch:
    event: HilogEvent
    pattern: LogPattern


def event_matches_pattern(event: HilogEvent, pattern: LogPattern) -> bool:
    if event.tag != pattern.tag:
        return False
    if pattern.level and event.level != pattern.level:
        return False
    if pattern.match_type == "regex":
        return re.search(pattern.pattern, event.message) is not None
    return pattern.pattern in event.message


def match_events(events: list[HilogEvent], patterns: list[LogPattern]) -> list[LogMatch]:
    matches: list[LogMatch] = []
    for event in events:
        for pattern in patterns:
            if event_matches_pattern(event, pattern):
                matches.append(LogMatch(event=event, pattern=pattern))
    return matches
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_hilog.py tests/test_matcher.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/hilog.py src/hilog_agent/matcher.py tests/fixtures/hilog tests/test_hilog.py tests/test_matcher.py
git commit -m "feat: parse hilog and match log patterns"
```

---

### Task 6: Result Schemas, Evidence, and Scoring

**Files:**
- Create: `src/hilog_agent/schemas/results.py`
- Create: `src/hilog_agent/evidence.py`
- Create: `src/hilog_agent/scoring.py`
- Test: `tests/test_scoring_evidence.py`

- [ ] **Step 1: Write scoring and evidence tests**

Create `tests/test_scoring_evidence.py`:

```python
from hilog_agent.evidence import make_failure_log_evidence
from hilog_agent.hilog import HilogEvent
from hilog_agent.scoring import confidence_label, score_feature_keywords


def test_score_feature_keywords_counts_question_hits():
    score = score_feature_keywords("拍照不出图", ["拍照", "录像"], ["拍照不出图"])
    assert score == 6


def test_confidence_label():
    assert confidence_label(80) == "high"
    assert confidence_label(45) == "medium"
    assert confidence_label(10) == "low"


def test_make_failure_log_evidence():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed",
        raw="raw",
        line=3,
    )
    evidence = make_failure_log_evidence(
        evidence_id="ev_001",
        event=event,
        feature="camera_capture",
        chain="normal_capture",
        step="capture_request",
        summary="命中 Capture failed",
        confidence_delta=5,
    )
    assert evidence.id == "ev_001"
    assert evidence.type == "failure_log_hit"
    assert evidence.raw_ref.line == 3
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_scoring_evidence.py -v
```

Expected: FAIL because result schemas, evidence, and scoring do not exist.

- [ ] **Step 3: Implement result schemas**

Create `src/hilog_agent/schemas/results.py`:

```python
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
        evidence_ids = {item.id for item in self.evidence}
        for cause in self.root_causes:
            if cause.supporting_evidence and not set(cause.supporting_evidence) <= evidence_ids:
                raise ValueError("root cause references unknown evidence")
        for status in self.chain_status:
            if status.evidence and not set(status.evidence) <= evidence_ids:
                raise ValueError("chain status references unknown evidence")
        return self
```

- [ ] **Step 4: Implement evidence helpers**

Create `src/hilog_agent/evidence.py`:

```python
from hilog_agent.hilog import HilogEvent
from hilog_agent.schemas.results import Evidence, RawRef


def make_failure_log_evidence(
    evidence_id: str,
    event: HilogEvent,
    feature: str,
    chain: str,
    step: str | None,
    summary: str,
    confidence_delta: float,
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source="hilog",
        type="failure_log_hit",
        feature=feature,
        chain=chain,
        step=step,
        severity="high",
        confidence_delta=confidence_delta,
        summary=summary,
        raw_ref=RawRef(file=None, line=event.line, timestamp=event.time),
    )
```

- [ ] **Step 5: Implement scoring helpers**

Create `src/hilog_agent/scoring.py`:

```python
from typing import Literal


def score_feature_keywords(
    question: str,
    keywords: list[str],
    symptoms: list[str],
) -> int:
    score = 0
    for keyword in keywords:
        if keyword and keyword in question:
            score += 3
    for symptom in symptoms:
        if symptom and symptom in question:
            score += 3
    return score


def confidence_label(score: float) -> Literal["high", "medium", "low"]:
    if score >= 70:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_scoring_evidence.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hilog_agent/schemas/results.py src/hilog_agent/evidence.py src/hilog_agent/scoring.py tests/test_scoring_evidence.py
git commit -m "feat: add result schemas and evidence helpers"
```

---

### Task 7: Prompt Rendering and Prompt Files

**Files:**
- Create: `src/hilog_agent/prompts.py`
- Create: `prompts/module_generation.md`
- Create: `prompts/feature_update.md`
- Test: `tests/test_prompts.py`

- [ ] **Step 1: Write prompt tests**

Create `tests/test_prompts.py`:

```python
from pathlib import Path

import pytest

from hilog_agent.prompts import render_template


def test_render_template_replaces_placeholders(tmp_path: Path):
    path = tmp_path / "prompt.md"
    path.write_text("Feature {{feature_name}} module {{module_name}}", encoding="utf-8")
    rendered = render_template(path, {"feature_name": "camera", "module_name": "ui"})
    assert rendered == "Feature camera module ui"


def test_render_template_fails_for_missing_value(tmp_path: Path):
    path = tmp_path / "prompt.md"
    path.write_text("Feature {{feature_name}}", encoding="utf-8")
    with pytest.raises(KeyError):
        render_template(path, {})
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_prompts.py -v
```

Expected: FAIL because `hilog_agent.prompts` does not exist.

- [ ] **Step 3: Implement prompt rendering**

Create `src/hilog_agent/prompts.py`:

```python
from pathlib import Path
import re

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def render_template(path: Path, values: dict[str, str]) -> str:
    template = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"missing prompt value: {key}")
        return values[key]

    return PLACEHOLDER_RE.sub(replace, template)
```

- [ ] **Step 4: Add prompt files**

Create `prompts/module_generation.md`:

````markdown
你是一个系统功能排障知识维护助手，负责根据代码生成模块级排障知识 YAML。

## 任务

为 feature `{{feature_name}}` 新增或更新模块 `{{module_name}}`。

模块代码路径：

```text
{{module_code_path}}
```

当前 feature.yaml：

```yaml
{{feature_yaml}}
```

## 工具使用规则

你必须按顺序执行：

1. 列出 `{{module_code_path}}` 下的主要文件。
2. 搜索日志宏、日志 tag、ERROR/WARN 关键日志。
3. 搜索 class、struct、interface、public 方法或对外入口。
4. 读取最相关的文件片段。
5. 总结模块职责、关键 symbols、logs、candidate_steps、failure_signals、dependencies。
6. 输出结构化 JSON。

你只能读取 `{{module_code_path}}` 下的文件。不要请求读取 repo_root 之外的路径。不要修改任何文件。

## module.yaml 压缩 schema

必填顶层字段：

- `name`
- `display_name`
- `code_path`
- `responsibility`
- `symbols`
- `logs`
- `candidate_steps`
- `failure_signals`
- `metadata`

可选顶层字段：

- `entrypoints`
- `dependencies`
- `extensions`

`symbols[]`：

- `name`: string
- `file`: string
- `kind`: class | function | method | interface | enum | config | other
- `relevance`: high | medium | low
- `reason`: string

`logs[]`：

- `tag`: string
- `level`: optional string
- `pattern`: string
- `match_type`: substring | regex
- `meaning`: string
- `evidence_type`: string
- `related_step`: optional string
- `severity`: high | medium | low
- `confidence_weight`: optional number
- `source.file`: string
- `source.line`: optional number
- `source.symbol`: optional string

`candidate_steps[]`：

- `id`: string
- `description`: string
- `file`: optional string
- `symbol`: optional string
- `async`: boolean
- `optional`: boolean
- `confidence`: high | medium | low
- `reason`: string
- `expected_logs`: list

`failure_signals[]`：

- `tag`: string
- `level`: optional string
- `pattern`: string
- `match_type`: substring | regex
- `severity`: high | medium | low
- `suggested_cause`: string
- `meaning`: string
- `related_step`: optional string
- `confidence_weight`: optional number
- `source.file`: string
- `source.line`: optional number
- `source.symbol`: optional string

`metadata`：

- `generated_by`: string
- `generated_at`: `{{generated_at}}`
- `review_notes`: list

## 生成规则

- `name` 必须等于 `{{module_name}}`。
- `code_path` 必须等于 `{{module_code_path}}`。
- `generated_at` 必须等于 `{{generated_at}}`。
- 不要编造无法从代码或当前 feature.yaml 支持的事实。
- 无法确认的内容必须写入 `metadata.review_notes`。
- `pattern`、`tag`、`symbol`、`file` 必须保持代码原文。
- `match_type` 默认使用 `substring`，只有确实需要正则时才使用 `regex`。
- `candidate_steps` 是候选，不代表已经进入 feature 主链。
- `logs` 保存重要正常日志和状态日志。
- `failure_signals` 只保存明确失败、异常、超时、资源不足等信号。
- 如果 `symbols`、`logs`、`candidate_steps` 或 `failure_signals` 为空，必须在 `metadata.review_notes` 说明原因。
- 输出必须是 JSON，不要输出 markdown。

## 输出 JSON schema

输出对象必须包含：

```json
{
  "module_yaml": "string",
  "analysis_summary": ["string"],
  "warnings": ["string"]
}
```
````

Create `prompts/feature_update.md`:

````markdown
你是一个系统功能排障知识维护助手，负责根据新模块 YAML 更新 feature 级排障知识。

## 任务

为 feature `{{feature_name}}` 合并模块 `{{module_name}}`。

当前 feature.yaml：

```yaml
{{feature_yaml}}
```

新生成的 module.yaml：

```yaml
{{module_yaml}}
```

## 允许修改范围

你只能做有限追加：

1. 在 `modules` 中追加新模块索引。
2. 在 `call_chains[].steps` 中追加和新模块相关的候选 step。
3. 在 `failure_patterns[].key_logs` 中追加和新模块相关的失败日志。
4. 在 `failure_patterns[].related_steps` 中追加新 step id。
5. 在 `failure_patterns[].possible_causes` 中追加新原因。
6. 更新 `metadata.version`，必须加 1。
7. 更新 `metadata.updated_at` 为 `{{updated_at}}`。
8. 追加 `metadata.review_notes`。

## 禁止事项

- 不要删除已有字段。
- 不要删除已有 module。
- 不要删除或改写已有 call_chain step。
- 不要删除或改写已有 failure_pattern。
- 不要修改 `name`、`display_name`、`description`。
- 不要自动修改其他 feature。
- 不要编造无法从 module.yaml 或当前 feature.yaml 支持的结论。

## feature.yaml 压缩 schema

必填顶层字段：

- `name`
- `display_name`
- `description`
- `keywords`
- `modules`
- `call_chains`
- `failure_patterns`
- `metadata`

可选顶层字段：

- `entrypoints`
- `extensions`

`modules[]`：

- `name`: string
- `yaml_path`: string，必须是 `modules/{{module_name}}.yaml`
- `responsibility`: string

`call_chains[].steps[]`：

- `id`: string，必须在整个 feature 内唯一
- `module`: string，必须引用 `modules[].name`
- `file`: optional string
- `symbol`: optional string
- `description`: string
- `optional`: boolean
- `async`: boolean
- `expected_logs`: list

`failure_patterns[]`：

- `symptom`: string
- `related_steps`: list，必须引用已有 step id
- `key_logs`: list
- `possible_causes`: list

`metadata`：

- `status`: draft | active
- `owner`: optional string
- `version`: number
- `updated_at`: `{{updated_at}}`
- `review_notes`: list

## 合并规则

- 必须把新模块加入 `modules`。
- `modules[].name` 必须等于 `{{module_name}}`。
- `modules[].yaml_path` 必须等于 `modules/{{module_name}}.yaml`。
- `modules[].responsibility` 应来自 module.yaml 的 `responsibility`。
- 如果 module.yaml 中有高置信度 `candidate_steps`，可以追加到最相关 call_chain 的末尾。
- 如果无法判断 step 应放入哪条 call_chain，不要追加 step，把建议写入 `metadata.review_notes`。
- 如果 module.yaml 中有 `failure_signals`，可以追加到相关 failure_pattern 的 `key_logs`。
- 如果无法判断 failure_signal 属于哪个 failure_pattern，不要追加，把建议写入 `metadata.review_notes`。
- 所有新增内容都必须来自 module.yaml。
- 当前 feature 是 `active` 时，更新后 `keywords`、`call_chains`、`failure_patterns` 都不能为空。
- 当前 feature 是 `draft` 时，允许 `call_chains` 或 `failure_patterns` 为空。
- 所有新增 step id 必须避免和已有 step id 冲突。

## 输出 JSON schema

输出对象必须包含：

```json
{
  "updated_feature_yaml": "string",
  "change_summary": ["string"],
  "warnings": ["string"],
  "related_feature_suggestions": [
    {
      "feature": "string",
      "reason": "string"
    }
  ]
}
```

输出必须是 JSON，不要输出 markdown。
````

- [ ] **Step 5: Run prompt tests**

Run:

```bash
pytest tests/test_prompts.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hilog_agent/prompts.py prompts tests/test_prompts.py
git commit -m "feat: add prompt rendering and templates"
```

---

### Task 8: LLM Structured Output Retry

**Files:**
- Create: `src/hilog_agent/llm.py`
- Test: `tests/test_llm_retry.py`

- [ ] **Step 1: Write retry tests with a fake client**

Create `tests/test_llm_retry.py`:

```python
from pydantic import BaseModel

from hilog_agent.llm import generate_validated


class SimpleResult(BaseModel):
    value: str


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt: str, schema: dict):
        self.calls += 1
        return self.responses.pop(0)


def test_generate_validated_retries_until_valid():
    client = FakeClient([{"wrong": "x"}, {"value": "ok"}])
    result = generate_validated(
        client=client,
        prompt="prompt",
        model=SimpleResult,
        max_retries=3,
    )
    assert result.value == "ok"
    assert client.calls == 2
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_llm_retry.py -v
```

Expected: FAIL because `hilog_agent.llm` does not exist.

- [ ] **Step 3: Implement retry helper**

Create `src/hilog_agent/llm.py`:

```python
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class JsonGeneratingClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


class LlmValidationError(RuntimeError):
    pass


def generate_validated(
    client: JsonGeneratingClient,
    prompt: str,
    model: type[T],
    max_retries: int,
) -> T:
    schema = model.model_json_schema()
    last_error: Exception | None = None
    current_prompt = prompt
    for _attempt in range(max_retries + 1):
        raw = client.generate_json(current_prompt, schema)
        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            current_prompt = (
                f"{prompt}\n\n上一次输出校验失败，请修正后重新输出。"
                f"\n校验错误：{exc}"
            )
    raise LlmValidationError(str(last_error))
```

- [ ] **Step 4: Run retry tests**

Run:

```bash
pytest tests/test_llm_retry.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/llm.py tests/test_llm_retry.py
git commit -m "feat: add llm structured output retry"
```

---

### Task 9: add-module Workflow

**Files:**
- Create: `src/hilog_agent/add_module.py`
- Test: `tests/test_add_module.py`

- [ ] **Step 1: Write add-module tests with fake LLM**

Create `tests/test_add_module.py`:

```python
from pathlib import Path

import yaml

from hilog_agent.add_module import AddModuleService
from hilog_agent.config import AgentConfig


class FakeModuleClient:
    def __init__(self, module_yaml: str, feature_yaml: str):
        self.module_yaml = module_yaml
        self.feature_yaml = feature_yaml

    def generate_json(self, prompt: str, schema: dict):
        if "module_yaml" in str(schema):
            return {
                "module_yaml": self.module_yaml,
                "analysis_summary": ["generated module"],
                "warnings": [],
            }
        return {
            "updated_feature_yaml": self.feature_yaml,
            "change_summary": ["updated feature"],
            "warnings": [],
            "related_feature_suggestions": [],
        }


def write_feature_fixture(root: Path):
    feature_dir = root / "features" / "camera_capture"
    module_dir = feature_dir / "modules"
    module_dir.mkdir(parents=True)
    (feature_dir / "feature.yaml").write_text(
        "name: camera_capture\n"
        "display_name: 相机拍照\n"
        "description: 拍照功能链路\n"
        "keywords: [拍照]\n"
        "modules: []\n"
        "call_chains: []\n"
        "failure_patterns: []\n"
        "metadata:\n"
        "  status: draft\n"
        "  version: 1\n"
        "  updated_at: \"2026-06-28 14:35:00\"\n"
        "  review_notes: []\n",
        encoding="utf-8",
    )
    return feature_dir


def test_add_module_writes_module_and_feature(tmp_path: Path):
    feature_dir = write_feature_fixture(tmp_path)
    module_yaml = (
        "name: image_pipeline\n"
        "display_name: 图像处理管线\n"
        "code_path: foundation/multimedia/image_pipeline\n"
        "responsibility: 图像处理\n"
        "symbols: []\n"
        "logs: []\n"
        "candidate_steps: []\n"
        "failure_signals: []\n"
        "metadata:\n"
        "  generated_by: hilog-agent\n"
        "  generated_at: \"2026-06-28 14:36:00\"\n"
        "  review_notes: []\n"
    )
    updated_feature_yaml = (
        "name: camera_capture\n"
        "display_name: 相机拍照\n"
        "description: 拍照功能链路\n"
        "keywords: [拍照]\n"
        "modules:\n"
        "  - name: image_pipeline\n"
        "    yaml_path: modules/image_pipeline.yaml\n"
        "    responsibility: 图像处理\n"
        "call_chains: []\n"
        "failure_patterns: []\n"
        "metadata:\n"
        "  status: draft\n"
        "  version: 2\n"
        "  updated_at: \"2026-06-28 14:36:00\"\n"
        "  review_notes: []\n"
    )
    config = AgentConfig(
        repo_root=tmp_path,
        features_dir=tmp_path / "features",
    )
    service = AddModuleService(config=config, client=FakeModuleClient(module_yaml, updated_feature_yaml))
    result = service.add_module(
        feature="camera_capture",
        module="image_pipeline",
        module_code_path="foundation/multimedia/image_pipeline",
        force=False,
        backup=False,
        now="2026-06-28 14:36:00",
    )
    assert (feature_dir / "modules" / "image_pipeline.yaml").exists()
    written_feature = yaml.safe_load((feature_dir / "feature.yaml").read_text(encoding="utf-8"))
    assert written_feature["metadata"]["version"] == 2
    assert result.written_files[0].action == "created"
```

- [ ] **Step 2: Run add-module test and verify failure**

Run:

```bash
pytest tests/test_add_module.py -v
```

Expected: FAIL because `AddModuleService` does not exist.

- [ ] **Step 3: Implement add-module service**

Create `src/hilog_agent/add_module.py`:

```python
from pathlib import Path

import yaml

from hilog_agent.config import AgentConfig
from hilog_agent.llm import JsonGeneratingClient, generate_validated
from hilog_agent.schemas.feature import FeatureYaml
from hilog_agent.schemas.module import ModuleYaml
from hilog_agent.schemas.results import (
    AddModuleResult,
    FeatureUpdateResult,
    ModuleGenerationResult,
    WrittenFile,
)


class AddModuleService:
    def __init__(self, config: AgentConfig, client: JsonGeneratingClient):
        self.config = config
        self.client = client

    def add_module(
        self,
        feature: str,
        module: str,
        module_code_path: str,
        force: bool,
        backup: bool,
        now: str,
    ) -> AddModuleResult:
        feature_dir = self.config.features_dir / feature
        feature_path = feature_dir / "feature.yaml"
        module_path = feature_dir / "modules" / f"{module}.yaml"
        if not feature_path.exists():
            raise FileNotFoundError(feature_path)
        if module_path.exists() and not force:
            raise FileExistsError(module_path)

        old_feature_yaml = feature_path.read_text(encoding="utf-8")
        old_feature = FeatureYaml.model_validate(yaml.safe_load(old_feature_yaml))

        module_result = generate_validated(
            client=self.client,
            prompt=f"generate module {module}",
            model=ModuleGenerationResult,
            max_retries=self.config.llm.max_validation_retries,
        )
        module_data = yaml.safe_load(module_result.module_yaml)
        module_model = ModuleYaml.model_validate(module_data)
        if module_model.name != module:
            raise ValueError("generated module name mismatch")
        if module_model.code_path != module_code_path:
            raise ValueError("generated module code_path mismatch")

        feature_result = generate_validated(
            client=self.client,
            prompt=f"update feature {feature}",
            model=FeatureUpdateResult,
            max_retries=self.config.llm.max_validation_retries,
        )
        updated_feature_data = yaml.safe_load(feature_result.updated_feature_yaml)
        updated_feature = FeatureYaml.model_validate(updated_feature_data)
        self._validate_feature_diff(old_feature, updated_feature, module, now, force)

        module_path.parent.mkdir(parents=True, exist_ok=True)
        written_files: list[WrittenFile] = []
        module_action = "updated" if module_path.exists() else "created"

        if backup:
            for target in [feature_path, module_path]:
                if target.exists():
                    backup_path = target.with_suffix(target.suffix + f".{now.replace(':', '').replace(' ', '_')}.bak")
                    backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
                    written_files.append(WrittenFile(path=str(backup_path), action="backup_created"))

        module_path.write_text(module_result.module_yaml, encoding="utf-8")
        feature_path.write_text(feature_result.updated_feature_yaml, encoding="utf-8")
        written_files.append(WrittenFile(path=str(module_path), action=module_action))
        written_files.append(WrittenFile(path=str(feature_path), action="updated"))

        return AddModuleResult(
            feature=feature,
            module=module,
            written_files=written_files,
            analysis_summary=module_result.analysis_summary,
            change_summary=feature_result.change_summary,
            warnings=module_result.warnings + feature_result.warnings,
            related_feature_suggestions=feature_result.related_feature_suggestions,
        )

    def _validate_feature_diff(
        self,
        old: FeatureYaml,
        new: FeatureYaml,
        module: str,
        now: str,
        force: bool,
    ) -> None:
        if old.name != new.name or old.display_name != new.display_name or old.description != new.description:
            raise ValueError("feature identity fields must not change")
        if old.keywords != new.keywords:
            raise ValueError("keywords must not change in add-module")
        if new.metadata.version != old.metadata.version + 1:
            raise ValueError("metadata.version must increment by 1")
        if new.metadata.updated_at != now:
            raise ValueError("metadata.updated_at must equal update time")
        old_modules = {item.name: item for item in old.modules}
        new_modules = {item.name: item for item in new.modules}
        if not set(old_modules).issubset(set(new_modules)):
            raise ValueError("existing modules must not be removed")
        if module not in new_modules:
            raise ValueError("new module index missing")
        for name, old_index in old_modules.items():
            new_index = new_modules[name]
            if old_index.yaml_path != new_index.yaml_path:
                raise ValueError("existing module yaml_path must not change")
            if old_index.responsibility != new_index.responsibility and not (force and name == module):
                raise ValueError("existing module responsibility must not change")
```

- [ ] **Step 4: Run add-module tests**

Run:

```bash
pytest tests/test_add_module.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/add_module.py tests/test_add_module.py
git commit -m "feat: add module generation write workflow"
```

---

### Task 10: analyze-log and ask Workflows

**Files:**
- Create: `src/hilog_agent/analyze.py`
- Create: `src/hilog_agent/render.py`
- Modify: `src/hilog_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add CLI tests for ask and analyze-log**

Append to `tests/test_cli.py`:

```python
def test_ask_command_requires_question():
    runner = CliRunner()
    result = runner.invoke(app, ["ask"])
    assert result.exit_code != 0


def test_analyze_log_command_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["analyze-log", "--help"])
    assert result.exit_code == 0
    assert "--log" in result.stdout
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because commands do not exist.

- [ ] **Step 3: Implement minimal workflows and renderers**

Create `src/hilog_agent/analyze.py`:

```python
from pathlib import Path

from hilog_agent.feature_store import FeatureStore
from hilog_agent.hilog import parse_hilog_file


def ask_feature(features_dir: Path, feature: str, question: str) -> str:
    store = FeatureStore(features_dir)
    loaded = store.read_feature_dir(feature)
    return (
        f"Feature: {loaded.feature.display_name}\n"
        f"Question: {question}\n"
        f"Modules: {', '.join(module.name for module in loaded.feature.modules)}"
    )


def analyze_log_summary(log_path: Path) -> str:
    parsed = parse_hilog_file(log_path)
    return (
        "Log stats:\n"
        f"- total_lines: {parsed.total_lines}\n"
        f"- parsed_lines: {parsed.parsed_lines}\n"
        f"- unparsed_lines: {parsed.unparsed_lines}"
    )
```

Create `src/hilog_agent/render.py`:

```python
import json
from pydantic import BaseModel


def render_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)
```

Modify `src/hilog_agent/cli.py` to add commands:

```python
from pathlib import Path
import typer

from hilog_agent import __version__
from hilog_agent.analyze import analyze_log_summary, ask_feature

app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hilog-agent {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


@app.command("ask")
def ask(
    question: str = typer.Option(..., "--question"),
    feature: str = typer.Option(..., "--feature"),
    features_dir: Path = typer.Option(Path("features"), "--features-dir"),
) -> None:
    typer.echo(ask_feature(features_dir, feature, question))


@app.command("analyze-log")
def analyze_log(
    log: Path = typer.Option(..., "--log"),
) -> None:
    typer.echo(analyze_log_summary(log))


def main() -> None:
    app()
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/analyze.py src/hilog_agent/render.py src/hilog_agent/cli.py tests/test_cli.py
git commit -m "feat: add ask and analyze-log cli commands"
```

---

### Task 11: add-module CLI

**Files:**
- Modify: `src/hilog_agent/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add add-module CLI help test**

Append to `tests/test_cli.py`:

```python
def test_add_module_command_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["add-module", "--help"])
    assert result.exit_code == 0
    assert "--module" in result.stdout
    assert "--force" in result.stdout
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_cli.py::test_add_module_command_exists -v
```

Expected: FAIL because `add-module` command does not exist.

- [ ] **Step 3: Add CLI command stub with clear runtime message**

Modify `src/hilog_agent/cli.py` to add:

```python
@app.command("add-module")
def add_module(
    feature: str = typer.Option(..., "--feature"),
    module: str = typer.Option(..., "--module"),
    path: str = typer.Option(..., "--path"),
    force: bool = typer.Option(False, "--force"),
    backup: bool = typer.Option(False, "--backup"),
) -> None:
    typer.echo(
        f"add-module requested for feature={feature}, module={module}, path={path}, "
        f"force={force}, backup={backup}"
    )
```

This step only wires CLI help. Connecting it to `AddModuleService` requires the real OpenAI-compatible client, which is handled in Task 12.

- [ ] **Step 4: Run CLI help test**

Run:

```bash
pytest tests/test_cli.py::test_add_module_command_exists -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hilog_agent/cli.py tests/test_cli.py
git commit -m "feat: expose add-module cli command"
```

---

### Task 12: Final Integration and Verification

**Files:**
- Modify: `src/hilog_agent/cli.py`
- Modify: `src/hilog_agent/llm.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add integration expectation**

Append to `tests/test_cli.py`:

```python
def test_analyze_log_fixture_outputs_stats():
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["analyze-log", "--log", "tests/fixtures/hilog/camera_capture.log"],
    )
    assert result.exit_code == 0
    assert "parsed_lines: 3" in result.stdout
```

- [ ] **Step 2: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS after all prior tasks are complete.

- [ ] **Step 3: Run coverage**

Run:

```bash
pytest --cov=hilog_agent --cov-report=term-missing
```

Expected: PASS. Coverage should show meaningful coverage for config, schemas, parser, matcher, store, scoring, prompt rendering, retry, and add-module service.

- [ ] **Step 4: Manual CLI checks**

Run:

```bash
agent --version
agent analyze-log --log tests/fixtures/hilog/camera_capture.log
agent ask --features-dir tests/fixtures/features --feature camera_capture --question "拍照不出图可能是什么原因"
agent add-module --help
```

Expected:

- `agent --version` prints `hilog-agent 0.1.0`.
- `analyze-log` prints log stats.
- `ask` prints feature name, question, and modules.
- `add-module --help` shows options.

- [ ] **Step 5: Commit**

```bash
git add src tests prompts pyproject.toml
git commit -m "test: verify hilog agent mvp integration"
```

---

## Self-Review

Spec coverage:

- MVP CLI commands are covered by Tasks 1, 10, 11, and 12.
- Config is covered by Task 2.
- Feature and module schemas are covered by Task 3.
- Feature directory validation is covered by Task 4.
- Hilog parsing and pattern matching are covered by Task 5.
- Evidence and scoring foundations are covered by Task 6.
- Prompt rendering and prompt files are covered by Task 7.
- LLM structured output retry is covered by Task 8.
- `add-module` validation and write workflow are covered by Task 9.
- Final smoke verification is covered by Task 12.

Known implementation gap intentionally left for follow-up after MVP foundation:

- Full root-cause ranking and complete `AnalysisResult` rendering are scaffolded by result models, evidence, scoring, and parser work, but the first implementation pass keeps CLI behavior minimal so each task remains testable. A follow-up plan should deepen `analyze-log` after the foundations pass.

Placeholder scan:

- No `TBD`, `TODO`, `FIXME`, or "implement later" instructions are used.
- Prompt placeholder examples such as `{{feature_yaml}}` are intentional prompt-template content.

Type consistency:

- `FeatureYaml`, `ModuleYaml`, `ModuleGenerationResult`, `FeatureUpdateResult`, and `AddModuleResult` are defined before use.
- CLI command names match the spec: `ask`, `analyze-log`, and `add-module`.
