import logging
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class JsonGeneratingClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


class LlmValidationError(RuntimeError):
    pass


def generate_validated(
    client: JsonGeneratingClient,
    prompt: str,
    model: type[T],
    max_retries: int,
) -> T:
    schema = model.model_json_schema()
    last_error: Exception | None = None
    current_prompt = prompt
    for _attempt in range(max_retries + 1):
        attempt = _attempt + 1
        logger.info("requesting LLM structured output model=%s attempt=%d", model.__name__, attempt)
        raw = client.generate_json(current_prompt, schema)
        try:
            result = model.model_validate(raw)
            logger.info("LLM structured output validated model=%s attempt=%d", model.__name__, attempt)
            return result
        except ValidationError as exc:
            last_error = exc
            logger.warning(
                "LLM structured output validation failed model=%s attempt=%d max_retries=%d",
                model.__name__,
                attempt,
                max_retries,
            )
            current_prompt = (
                f"{prompt}\n\n上一次输出校验失败，请修正后重新输出。"
                f"\n校验错误：{exc}"
            )
    logger.error("LLM structured output exhausted retries model=%s max_retries=%d", model.__name__, max_retries)
    raise LlmValidationError(str(last_error))
