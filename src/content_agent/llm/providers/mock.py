from content_agent.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Deterministic mock LLM provider for tests. Returns fixed responses."""

    def __init__(self, response: str = "mock_llm_response") -> None:
        self._response = response

    async def complete(self, system_prompt: str, user_message: str) -> str:
        return self._response
