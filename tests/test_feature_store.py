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
