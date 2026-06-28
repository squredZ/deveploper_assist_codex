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


def test_call_chain_step_accepts_async_alias_and_serializes_alias():
    feature = FeatureYaml.model_validate(valid_feature_data())

    step_dump = feature.model_dump()["call_chains"][0]["steps"][0]
    assert step_dump["async"] is False
    assert "async_" not in step_dump


def test_call_chain_step_accepts_async_field_name():
    data = valid_feature_data()
    step = data["call_chains"][0]["steps"][0]
    step["async_"] = step.pop("async")

    feature = FeatureYaml.model_validate(data)

    assert feature.call_chains[0].steps[0].async_ is False
    step_dump = feature.model_dump()["call_chains"][0]["steps"][0]
    assert step_dump["async"] is False
    assert "async_" not in step_dump


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
