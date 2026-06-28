from pathlib import Path

import yaml

from hilog_agent.config import AgentConfig
from hilog_agent.llm import JsonGeneratingClient, generate_validated
from hilog_agent.schemas.common import validate_relative_path
from hilog_agent.schemas.feature import FeatureYaml
from hilog_agent.schemas.module import ModuleYaml
from hilog_agent.schemas.results import (
    AddModuleResult,
    FeatureUpdateResult,
    ModuleGenerationResult,
    WrittenFile,
)


class AddModuleService:
    def __init__(self, config: AgentConfig, client: JsonGeneratingClient):
        self.config = config
        self.client = client

    def add_module(
        self,
        feature: str,
        module: str,
        module_code_path: str,
        force: bool,
        backup: bool,
        now: str,
    ) -> AddModuleResult:
        _validate_simple_name(feature, "feature")
        _validate_simple_name(module, "module")
        validate_relative_path(module_code_path)

        feature_dir = self.config.features_dir / feature
        feature_path = feature_dir / "feature.yaml"
        module_path = feature_dir / "modules" / f"{module}.yaml"
        if not feature_path.exists():
            raise FileNotFoundError(feature_path)
        if module_path.exists() and not force:
            raise FileExistsError(module_path)

        old_feature_yaml = feature_path.read_text(encoding="utf-8")
        old_feature = FeatureYaml.model_validate(yaml.safe_load(old_feature_yaml))

        module_result = generate_validated(
            client=self.client,
            prompt=f"generate module {module}",
            model=ModuleGenerationResult,
            max_retries=self.config.llm.max_validation_retries,
        )
        module_data = yaml.safe_load(module_result.module_yaml)
        module_model = ModuleYaml.model_validate(module_data)
        if module_model.name != module:
            raise ValueError("generated module name mismatch")
        if module_model.code_path != module_code_path:
            raise ValueError("generated module code_path mismatch")

        feature_result = generate_validated(
            client=self.client,
            prompt=f"update feature {feature}",
            model=FeatureUpdateResult,
            max_retries=self.config.llm.max_validation_retries,
        )
        updated_feature_data = yaml.safe_load(feature_result.updated_feature_yaml)
        updated_feature = FeatureYaml.model_validate(updated_feature_data)
        self._validate_feature_diff(old_feature, updated_feature, module, now, force)

        module_path.parent.mkdir(parents=True, exist_ok=True)
        written_files: list[WrittenFile] = []
        module_action = "updated" if module_path.exists() else "created"

        if backup:
            for target in [feature_path, module_path]:
                if target.exists():
                    backup_path = target.with_suffix(
                        target.suffix + f".{now.replace(':', '').replace(' ', '_')}.bak"
                    )
                    backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
                    written_files.append(WrittenFile(path=str(backup_path), action="backup_created"))

        module_path.write_text(module_result.module_yaml, encoding="utf-8")
        feature_path.write_text(feature_result.updated_feature_yaml, encoding="utf-8")
        written_files.append(WrittenFile(path=str(module_path), action=module_action))
        written_files.append(WrittenFile(path=str(feature_path), action="updated"))

        return AddModuleResult(
            feature=feature,
            module=module,
            written_files=written_files,
            analysis_summary=module_result.analysis_summary,
            change_summary=feature_result.change_summary,
            warnings=module_result.warnings + feature_result.warnings,
            related_feature_suggestions=feature_result.related_feature_suggestions,
        )

    def _validate_feature_diff(
        self,
        old: FeatureYaml,
        new: FeatureYaml,
        module: str,
        now: str,
        force: bool,
    ) -> None:
        if old.name != new.name or old.display_name != new.display_name or old.description != new.description:
            raise ValueError("feature identity fields must not change")
        if old.keywords != new.keywords:
            raise ValueError("keywords must not change in add-module")
        if new.metadata.version != old.metadata.version + 1:
            raise ValueError("metadata.version must increment by 1")
        if new.metadata.updated_at != now:
            raise ValueError("metadata.updated_at must equal update time")
        if old.metadata.status != new.metadata.status:
            raise ValueError("metadata.status must not change")
        if old.metadata.owner != new.metadata.owner:
            raise ValueError("metadata.owner must not change")

        old_modules = {item.name: item for item in old.modules}
        new_modules = {item.name: item for item in new.modules}
        if not set(old_modules).issubset(set(new_modules)):
            raise ValueError("existing modules must not be removed")
        if module not in new_modules:
            raise ValueError("new module index missing")
        for name, old_index in old_modules.items():
            new_index = new_modules[name]
            if old_index.yaml_path != new_index.yaml_path:
                raise ValueError("existing module yaml_path must not change")
            if old_index.responsibility != new_index.responsibility and not (force and name == module):
                raise ValueError("existing module responsibility must not change")

        self._validate_call_chains_append_only(old, new)
        self._validate_failure_patterns_append_only(old, new)
        if not _is_prefix(old.metadata.review_notes, new.metadata.review_notes):
            raise ValueError("metadata.review_notes can only be appended")

    def _validate_call_chains_append_only(self, old: FeatureYaml, new: FeatureYaml) -> None:
        old_chains = {chain.name: chain for chain in old.call_chains}
        new_chains = {chain.name: chain for chain in new.call_chains}
        if set(old_chains) != set(new_chains):
            raise ValueError("call_chains cannot be added or removed in add-module")
        for name, old_chain in old_chains.items():
            new_chain = new_chains[name]
            if old_chain.description != new_chain.description or old_chain.keywords != new_chain.keywords:
                raise ValueError("existing call_chain metadata must not change")
            if not _is_prefix(
                [step.model_dump() for step in old_chain.steps],
                [step.model_dump() for step in new_chain.steps],
            ):
                raise ValueError("existing call_chain steps must not change")

    def _validate_failure_patterns_append_only(self, old: FeatureYaml, new: FeatureYaml) -> None:
        if len(new.failure_patterns) != len(old.failure_patterns):
            raise ValueError("failure_patterns cannot be added or removed in add-module")
        for old_pattern, new_pattern in zip(old.failure_patterns, new.failure_patterns, strict=True):
            if old_pattern.symptom != new_pattern.symptom:
                raise ValueError("existing failure_pattern symptom must not change")
            if not _is_prefix(old_pattern.related_steps, new_pattern.related_steps):
                raise ValueError("failure_pattern related_steps can only be appended")
            if not _is_prefix(
                [log.model_dump() for log in old_pattern.key_logs],
                [log.model_dump() for log in new_pattern.key_logs],
            ):
                raise ValueError("failure_pattern key_logs can only be appended")
            if not _is_prefix(old_pattern.possible_causes, new_pattern.possible_causes):
                raise ValueError("failure_pattern possible_causes can only be appended")


def _is_prefix(old_values: list, new_values: list) -> bool:
    return len(old_values) <= len(new_values) and new_values[: len(old_values)] == old_values


def _validate_simple_name(value: str, label: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or Path(value).is_absolute()
    ):
        raise ValueError(f"invalid {label} name: {value}")
    return value
