from pathlib import Path
import logging
import re

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
logger = logging.getLogger(__name__)


def render_template(path: Path, values: dict[str, str]) -> str:
    logger.info("rendering prompt template path=%s variables=%d", path, len(values))
    template = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            logger.error("missing prompt template value key=%s path=%s", key, path)
            raise KeyError(f"missing prompt value: {key}")
        return values[key]

    rendered = PLACEHOLDER_RE.sub(replace, template)
    logger.info("rendered prompt template path=%s chars=%d", path, len(rendered))
    return rendered
