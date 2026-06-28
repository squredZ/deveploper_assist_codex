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
