from dataclasses import dataclass
from pathlib import Path

import yaml

from hilog_agent.schemas.feature import FeatureYaml
from hilog_agent.schemas.module import ModuleYaml


def _is_simple_feature_name(feature_name: str) -> bool:
    return not (
        not feature_name
        or feature_name in {".", ".."}
        or "/" in feature_name
        or "\\" in feature_name
        or Path(feature_name).is_absolute()
    )


def _validate_feature_name(feature_name: str) -> str:
    if not _is_simple_feature_name(feature_name):
        raise ValueError(f"invalid feature name: {feature_name}")
    return feature_name


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
            if path.is_dir()
            and (path / "feature.yaml").exists()
            and _is_simple_feature_name(path.name)
        ]
        return sorted(names)

    def read_feature_dir(self, feature_name: str) -> LoadedFeature:
        _validate_feature_name(feature_name)
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
