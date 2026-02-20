"""Local stub for the Emergent platform's LLM integration.
When deployed on Emergent cloud, the real package provides LLM access.
Locally, research analysis falls back to the server.py fallback logic.
"""

class UserMessage:
    def __init__(self, text: str = ""):
        self.text = text

class LlmChat:
    def __init__(self, api_key: str = "", session_id: str = "", system_message: str = ""):
        self._model_provider = None
        self._model_name = None

    def with_model(self, provider: str, model: str):
        self._model_provider = provider
        self._model_name = model
        return self

    async def send_message(self, message: UserMessage) -> str:
        raise Exception("LLM not available locally - using fallback analysis")
