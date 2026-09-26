import pytest

from llm import extract_json, resolve_config


@pytest.mark.parametrize("raw", [
    '{"prob_up_7d": 55}',
    '```json\n{"prob_up_7d": 55}\n```',
    '<think>hmm {not json}</think>\n{"prob_up_7d": 55}',
    'Sure! Here you go: {"prob_up_7d": 55} Hope that helps.',
])
def test_extract_json_variants(raw):
    assert extract_json(raw) == {"prob_up_7d": 55}


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        extract_json("no json here")
    with pytest.raises(ValueError):
        extract_json("")


def test_resolve_config_precedence(monkeypatch):
    for var in ("LLM_PROVIDER", "OPENAI_MODEL", "OLLAMA_MODEL", "DEEPSEEK_MODEL", "LLM_TEMPERATURE", "LLM_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)

    assert resolve_config().label == "openai/gpt-4.1"

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    assert resolve_config().label == "ollama/llama3.1:8b"

    # CLI provider wins, and its own default model applies (not OLLAMA_MODEL).
    assert resolve_config("deepseek").label == "deepseek/deepseek-chat"
    assert resolve_config("deepseek", "deepseek-reasoner").model == "deepseek-reasoner"


def test_resolve_config_unknown_provider():
    with pytest.raises(ValueError):
        resolve_config("nope")
