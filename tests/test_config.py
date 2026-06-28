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
