from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "feature_name",
    ["../camera_capture", "camera/capture", "camera\\capture", "..", "", "/camera_capture"],
)
def test_read_feature_dir_rejects_non_simple_feature_names(feature_name: str):
    store = FeatureStore(Path("tests/fixtures/features"))

    with pytest.raises(ValueError):
        store.read_feature_dir(feature_name)


def test_list_features_filters_non_simple_child_names(tmp_path: Path):
    (tmp_path / "camera_capture").mkdir()
    (tmp_path / "camera_capture" / "feature.yaml").write_text("name: camera_capture\n")
    (tmp_path / "bad\\name").mkdir()
    (tmp_path / "bad\\name" / "feature.yaml").write_text("name: bad\n")

    store = FeatureStore(tmp_path)

    assert store.list_features() == ["camera_capture"]
