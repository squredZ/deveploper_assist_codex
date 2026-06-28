from pathlib import Path
import logging

from hilog_agent.feature_store import FeatureStore
from hilog_agent.hilog import parse_hilog_file

logger = logging.getLogger(__name__)


def ask_feature(features_dir: Path, feature: str, question: str) -> str:
    logger.info("answering feature question feature=%s features_dir=%s", feature, features_dir)
    store = FeatureStore(features_dir)
    loaded = store.read_feature_dir(feature)
    logger.info("prepared feature answer feature=%s modules=%d", feature, len(loaded.feature.modules))
    return (
        f"Feature: {loaded.feature.display_name}\n"
        f"Question: {question}\n"
        f"Modules: {', '.join(module.name for module in loaded.feature.modules)}"
    )


def analyze_log_summary(log_path: Path) -> str:
    logger.info("building analyze-log summary path=%s", log_path)
    parsed = parse_hilog_file(log_path)
    return (
        "Log stats:\n"
        f"- total_lines: {parsed.total_lines}\n"
        f"- parsed_lines: {parsed.parsed_lines}\n"
        f"- unparsed_lines: {parsed.unparsed_lines}"
    )
