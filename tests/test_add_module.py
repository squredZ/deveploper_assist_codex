from pathlib import Path

import pytest
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


@pytest.mark.parametrize(
    ("feature", "module", "module_code_path"),
    [
        ("../camera_capture", "image_pipeline", "foundation/multimedia/image_pipeline"),
        ("camera_capture", "../image_pipeline", "foundation/multimedia/image_pipeline"),
        ("camera_capture", "image_pipeline", "../foundation/multimedia/image_pipeline"),
    ],
)
def test_add_module_rejects_path_escape_inputs(
    tmp_path: Path,
    feature: str,
    module: str,
    module_code_path: str,
):
    write_feature_fixture(tmp_path)
    config = AgentConfig(
        repo_root=tmp_path,
        features_dir=tmp_path / "features",
    )
    service = AddModuleService(config=config, client=FakeModuleClient("", ""))

    with pytest.raises(ValueError):
        service.add_module(
            feature=feature,
            module=module,
            module_code_path=module_code_path,
            force=False,
            backup=False,
            now="2026-06-28 14:36:00",
        )
