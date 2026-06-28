# Hilog Agent

Hilog Agent is a Python CLI for maintaining feature troubleshooting knowledge and analyzing hilog files. The MVP focuses on three workflows:

- Feature Q&A from structured `feature.yaml` knowledge.
- Hilog parsing and basic log statistics.
- LLM-assisted module knowledge generation and feature YAML updates.

The project is intentionally small: deterministic parsing, schema validation, and evidence models are implemented first; deeper LLM-driven analysis can build on these foundations.

## Requirements

- Python 3.11+
- A virtual environment is recommended.

Runtime dependencies are declared in `pyproject.toml`:

- `typer`
- `pydantic`
- `pyyaml`
- `openai`

Development dependencies:

- `pytest`
- `pytest-cov`

## Setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

If a virtual environment already exists, install or refresh dependencies with:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

## Verification

Run the test suite:

```bash
.venv/bin/pytest -v
```

Run coverage:

```bash
.venv/bin/pytest --cov=hilog_agent --cov-report=term-missing
```

Basic CLI checks:

```bash
.venv/bin/agent --version
.venv/bin/agent analyze-log --log tests/fixtures/hilog/camera_capture.log
.venv/bin/agent ask --features-dir tests/fixtures/features --feature camera_capture --question "拍照不出图可能是什么原因"
.venv/bin/agent add-module --help
```

## CLI Usage

### Version

```bash
agent --version
```

### Feature Q&A

```bash
agent ask \
  --features-dir tests/fixtures/features \
  --feature camera_capture \
  --question "拍照不出图可能是什么原因"
```

Current MVP output is a deterministic feature summary.

### Hilog Analysis

```bash
agent analyze-log \
  --log tests/fixtures/hilog/camera_capture.log
```

Current MVP output reports parsed/unparsed line statistics. The parser supports year-bearing timestamps such as:

```text
2026-06-28 14:35:01.120  1234  5678 I CameraUI: click capture
```

### Add Module

```bash
agent add-module \
  --feature camera_capture \
  --module image_pipeline \
  --path foundation/multimedia/image_pipeline
```

The service layer supports LLM-generated module YAML and feature YAML updates with validation and write safety checks. The current CLI command exposes the MVP options and is ready to be connected to a real OpenAI-compatible client.

## Logging

The CLI uses Python `logging`.

Default mode shows only warnings and errors:

```bash
agent analyze-log --log tests/fixtures/hilog/camera_capture.log
```

Verbose mode enables info-level tracing:

```bash
agent --verbose analyze-log --log tests/fixtures/hilog/camera_capture.log
```

Key paths log useful trace points:

- Config loading
- Feature directory reads
- Hilog parsing and time filtering
- Log matching
- LLM structured-output retries
- `add-module` validation and writes
- Prompt rendering
- CLI command entrypoints

Secrets such as API keys should not be logged.

## Configuration

Optional config file: `agent.yaml`.

Example:

```yaml
repo_root: /path/to/source
features_dir: ./features
log_temp_dir: ./.tmp/hilog-agent

output:
  format: text
  verbose: false

llm:
  enabled: true
  provider: openai_compatible
  api_key_env: OPENAI_API_KEY
  api_key: null
  base_url: https://api.openai.com/v1
  model: gpt-5.5
  structured_output: json_schema
  max_validation_retries: 3
  reasoning:
    effort: medium
    summary: auto
```

Prefer `api_key_env` over plaintext `api_key`. If plaintext `api_key` is present, config loading logs a warning.

## Feature Knowledge Layout

Feature knowledge uses a directory layout:

```text
features/
  camera_capture/
    feature.yaml
    modules/
      camera_ui.yaml
      camera_framework.yaml
```

`feature.yaml` owns feature-level knowledge:

- Display name and description
- Keywords
- Module index
- Entrypoints
- Call chains
- Failure patterns
- Metadata

`modules/<module>.yaml` owns module-level knowledge:

- Code path
- Responsibility
- Symbols
- Logs
- Candidate steps
- Failure signals
- Dependencies
- Review notes

Schemas are implemented with Pydantic v2 and validated before use.

## Project Structure

```text
src/hilog_agent/
  add_module.py      # add-module service, validation, write workflow
  analyze.py         # ask/analyze-log MVP workflows
  cli.py             # Typer CLI and logging setup
  config.py          # agent.yaml config models/loading
  evidence.py        # evidence helper functions
  feature_store.py   # feature directory loading and cross-file validation
  hilog.py           # hilog parsing and time filtering
  llm.py             # structured-output validation retry helper
  matcher.py         # log pattern matching
  prompts.py         # prompt template rendering
  render.py          # JSON rendering helper
  schemas/           # Pydantic schemas

prompts/
  module_generation.md
  feature_update.md

tests/
  fixtures/
  test_*.py
```

## Design Docs

Detailed design and implementation plan:

- `docs/superpowers/specs/2026-06-28-hilog-agent-design.md`
- `docs/superpowers/plans/2026-06-28-hilog-agent.md`

The original design draft may also exist locally as:

- `docs/feature_hilog_agent_design.md`

## Current MVP Boundaries

Implemented:

- CLI scaffold
- Config models and loading
- Feature/module schemas
- Feature directory validation
- Hilog parsing and matching
- Evidence/result models
- Prompt templates
- Structured-output retry helper
- `add-module` service workflow
- Key runtime logging
- Unit and CLI smoke tests

Not yet fully implemented:

- Full root-cause ranking in `analyze-log`
- Full bounded ReAct orchestrator connected to a real LLM client
- Real `add-module` CLI execution with OpenAI-compatible client wiring
- Cross-feature automatic updates
- `remove-module`
- Web UI
