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
