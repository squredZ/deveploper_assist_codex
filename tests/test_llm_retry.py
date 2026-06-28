from pydantic import BaseModel

from hilog_agent.llm import generate_validated


class SimpleResult(BaseModel):
    value: str


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt: str, schema: dict):
        self.calls += 1
        return self.responses.pop(0)


def test_generate_validated_retries_until_valid():
    client = FakeClient([{"wrong": "x"}, {"value": "ok"}])
    result = generate_validated(
        client=client,
        prompt="prompt",
        model=SimpleResult,
        max_retries=3,
    )
    assert result.value == "ok"
    assert client.calls == 2
