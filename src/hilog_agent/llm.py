from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


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
        raw = client.generate_json(current_prompt, schema)
        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            current_prompt = (
                f"{prompt}\n\n上一次输出校验失败，请修正后重新输出。"
                f"\n校验错误：{exc}"
            )
    raise LlmValidationError(str(last_error))
