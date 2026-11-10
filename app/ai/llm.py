import httpx

from app.core.config import get_settings
from app.services.usage import AiCallResult, estimate_tokens


class LLMClient:
    """Interfaz mínima de un proveedor de chat."""

    def complete(
        self, messages: list[dict[str, str]], *, model: str, max_tokens: int
    ) -> AiCallResult:
        raise NotImplementedError


class GroqClient(LLMClient):
    """Cliente compatible con la API de OpenAI de Groq."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(
        self, messages: list[dict[str, str]], *, model: str, max_tokens: int
    ) -> AiCallResult:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        if not usage:
            prompt_text = "\n".join(message["content"] for message in messages)
            return AiCallResult(
                tokens_in=estimate_tokens(prompt_text),
                tokens_out=estimate_tokens(content),
                estimated=True,
                content=content,
            )
        return AiCallResult(
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            content=content,
        )


class FakeLLMClient(LLMClient):
    """Cliente determinista para desarrollo y pruebas sin red."""

    def __init__(self, reply: str = "Respuesta de prueba") -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []

    def complete(
        self, messages: list[dict[str, str]], *, model: str, max_tokens: int
    ) -> AiCallResult:
        self.calls.append(messages)
        prompt_text = "\n".join(message["content"] for message in messages)
        return AiCallResult(
            tokens_in=estimate_tokens(prompt_text),
            tokens_out=estimate_tokens(self.reply),
            estimated=True,
            content=self.reply,
        )


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.groq_api_key:
        return GroqClient(settings.groq_api_key)
    if settings.env in {"development", "test"}:
        return FakeLLMClient(
            "Configura GROQ_API_KEY para obtener respuestas reales del modelo."
        )
    raise RuntimeError("GROQ_API_KEY no configurada")
