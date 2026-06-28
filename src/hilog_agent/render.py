import json
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def render_json(model: BaseModel) -> str:
    logger.info("rendering model as json model=%s", type(model).__name__)
    return json.dumps(model.model_dump(), ensure_ascii=False, indent=2)
