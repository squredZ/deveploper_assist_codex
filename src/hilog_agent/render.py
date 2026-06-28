import json

from pydantic import BaseModel


def render_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)
