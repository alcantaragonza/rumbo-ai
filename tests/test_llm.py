from app.ai.llm import FakeLLMClient


def test_fake_llm_works_without_network() -> None:
    client = FakeLLMClient("Hola desde el catálogo")

    result = client.complete(
        [{"role": "user", "content": "¿Qué puedo visitar?"}],
        model="fake",
        max_tokens=10,
    )

    assert result.content == "Hola desde el catálogo"
    assert result.tokens_total > 0
    assert client.calls
