# llm.py
"""
Provider-agnostic JSON completions for OpenAI, DeepSeek and Ollama.

Selection precedence (highest first):
  provider: CLI flag -> LLM_PROVIDER env -> "openai"
  model:    CLI flag -> <PROVIDER>_MODEL env (OPENAI_MODEL, DEEPSEEK_MODEL, OLLAMA_MODEL) -> provider default
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDERS: Dict[str, Dict] = {
    "openai": {
        "default_model": "gpt-4.1",
        "base_url": None,
        "key_env": "OPENAI_API_KEY",
        "timeout": 120,
    },
    "deepseek": {
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "timeout": 300,
    },
    "ollama": {
        "default_model": "qwen3.5:9b",
        "base_url": "http://localhost:11434",
        "key_env": None,
        "timeout": 900,  # local models on modest hardware can be slow
    },
}


@dataclass
class LLMConfig:
    provider: str
    model: str
    temperature: float
    timeout: float

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}"


def resolve_config(provider: Optional[str] = None, model: Optional[str] = None) -> LLMConfig:
    provider = (provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider '{provider}'. Choose from: {', '.join(PROVIDERS)}")

    spec = PROVIDERS[provider]
    model = model or os.getenv(f"{provider.upper()}_MODEL") or spec["default_model"]
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    timeout = float(os.getenv("LLM_TIMEOUT", spec["timeout"]))
    return LLMConfig(provider=provider, model=model, temperature=temperature, timeout=timeout)


def extract_json(text: str) -> Dict:
    """
    Parse a JSON object out of model output, tolerating <think> blocks and code fences
    (common with reasoning models such as deepseek-r1 / qwen3 served by Ollama).
    """
    if not text:
        raise ValueError("Model returned an empty response")

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
        parsed = json.loads(cleaned[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON is not an object")
    return parsed


def _complete_openai_compatible(messages: List[Dict], config: LLMConfig) -> str:
    from openai import BadRequestError, OpenAI

    spec = PROVIDERS[config.provider]
    api_key = os.getenv(spec["key_env"])
    if not api_key:
        raise RuntimeError(f"{spec['key_env']} is not set; required for provider '{config.provider}'")

    base_url = os.getenv(f"{config.provider.upper()}_BASE_URL") or spec["base_url"]
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=config.timeout)

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            response_format={"type": "json_object"},
        )
    except BadRequestError as exc:
        # Reasoning models (o-series, gpt-5, deepseek-reasoner) may reject temperature
        # or JSON mode; retry with plain defaults and rely on extract_json.
        print(f"⚠️ {config.label} rejected JSON mode/temperature ({exc}); retrying with defaults.")
        response = client.chat.completions.create(model=config.model, messages=messages)

    return response.choices[0].message.content or ""


def _complete_ollama(messages: List[Dict], config: LLMConfig) -> str:
    # Native API rather than /v1 so we can raise num_ctx; Ollama's small default context
    # would silently truncate the market payload.
    base_url = (os.getenv("OLLAMA_BASE_URL") or PROVIDERS["ollama"]["base_url"]).rstrip("/")
    base_url = re.sub(r"/v1$", "", base_url)

    body = {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": config.temperature,
            "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "16384")),
        },
    }
    # Thinking models (qwen3.x, deepseek-r1) run ~15x slower with thinking on; off by default.
    think = os.getenv("OLLAMA_THINK", "false").strip().lower()
    if think in ("true", "false"):
        body["think"] = think == "true"

    response = requests.post(f"{base_url}/api/chat", json=body, timeout=config.timeout)
    if not response.ok:
        raise RuntimeError(f"Ollama error {response.status_code}: {response.text[:300]}")
    return response.json().get("message", {}).get("content", "")


def complete_json(system: str, user: str, config: LLMConfig) -> Tuple[Dict, str]:
    """Return (parsed JSON object, raw text) from the configured provider."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if config.provider == "ollama":
        raw = _complete_ollama(messages, config)
    else:
        raw = _complete_openai_compatible(messages, config)
    return extract_json(raw), raw
