from pathlib import Path

from hilog_agent.feature_store import FeatureStore
from hilog_agent.hilog import parse_hilog_file


def ask_feature(features_dir: Path, feature: str, question: str) -> str:
    store = FeatureStore(features_dir)
    loaded = store.read_feature_dir(feature)
    return (
        f"Feature: {loaded.feature.display_name}\n"
        f"Question: {question}\n"
        f"Modules: {', '.join(module.name for module in loaded.feature.modules)}"
    )


def analyze_log_summary(log_path: Path) -> str:
    parsed = parse_hilog_file(log_path)
    return (
        "Log stats:\n"
        f"- total_lines: {parsed.total_lines}\n"
        f"- parsed_lines: {parsed.parsed_lines}\n"
        f"- unparsed_lines: {parsed.unparsed_lines}"
    )
