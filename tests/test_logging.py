import logging
from pathlib import Path

from pydantic import BaseModel

from hilog_agent.add_module import AddModuleService
from hilog_agent.cli import configure_logging
from hilog_agent.config import AgentConfig, load_config
from hilog_agent.feature_store import FeatureStore
from hilog_agent.hilog import parse_hilog_file
from hilog_agent.llm import generate_validated


class SimpleResult(BaseModel):
    value: str


class RetryClient:
    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt: str, schema: dict):
        self.calls += 1
        if self.calls == 1:
            return {"wrong": "x"}
        return {"value": "ok"}


class AddModuleClient:
    def __init__(self, module_yaml: str, feature_yaml: str):
        self.module_yaml = module_yaml
        self.feature_yaml = feature_yaml

    def generate_json(self, prompt: str, schema: dict):
        if "module_yaml" in str(schema):
            return {"module_yaml": self.module_yaml, "analysis_summary": [], "warnings": []}
        return {
            "updated_feature_yaml": self.feature_yaml,
            "change_summary": [],
            "warnings": [],
            "related_feature_suggestions": [],
        }


def test_configure_logging_sets_info_level_for_verbose():
    configure_logging(verbose=True)
    assert logging.getLogger().level == logging.INFO


def test_load_config_logs_default_path(caplog, tmp_path: Path):
    caplog.set_level(logging.INFO)

    load_config(tmp_path / "missing.yaml")

    assert "config file not found; using defaults" in caplog.text


def test_feature_store_logs_read_summary(caplog):
    caplog.set_level(logging.INFO)
    store = FeatureStore(Path("tests/fixtures/features"))

    store.read_feature_dir("camera_capture")

    assert "reading feature directory" in caplog.text
    assert "loaded feature directory" in caplog.text
    assert "modules=1" in caplog.text


def test_hilog_parser_logs_parse_summary(caplog):
    caplog.set_level(logging.INFO)

    parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))

    assert "parsed hilog file" in caplog.text
    assert "parsed_lines=3" in caplog.text
    assert "unparsed_lines=1" in caplog.text


def test_llm_retry_logs_validation_failure(caplog):
    caplog.set_level(logging.INFO)

    result = generate_validated(
        client=RetryClient(),
        prompt="prompt",
        model=SimpleResult,
        max_retries=3,
    )

    assert result.value == "ok"
    assert "LLM structured output validation failed" in caplog.text
    assert "LLM structured output validated" in caplog.text


def test_add_module_logs_write_summary(caplog, tmp_path: Path):
    caplog.set_level(logging.INFO)
    feature_dir = tmp_path / "features" / "camera_capture"
    (feature_dir / "modules").mkdir(parents=True)
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
    service = AddModuleService(
        config=AgentConfig(repo_root=tmp_path, features_dir=tmp_path / "features"),
        client=AddModuleClient(module_yaml, updated_feature_yaml),
    )

    result = service.add_module(
        feature="camera_capture",
        module="image_pipeline",
        module_code_path="foundation/multimedia/image_pipeline",
        force=False,
        backup=False,
        now="2026-06-28 14:36:00",
    )

    assert len(result.written_files) == 2
    assert "starting add-module" in caplog.text
    assert "validated generated module yaml" in caplog.text
    assert "wrote add-module outputs" in caplog.text
