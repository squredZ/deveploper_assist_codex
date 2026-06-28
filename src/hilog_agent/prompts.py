from pathlib import Path
import re

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def render_template(path: Path, values: dict[str, str]) -> str:
    template = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"missing prompt value: {key}")
        return values[key]

    return PLACEHOLDER_RE.sub(replace, template)
