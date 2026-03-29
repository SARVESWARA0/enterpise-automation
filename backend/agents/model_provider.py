"""
Central Strands model factory for all agents.

Default provider is OpenAI. Set ``STRANDS_MODEL_PROVIDER=ollama`` to use a local
Ollama server (see Strands ``OllamaModel`` docs). Ollama support requires
``pip install 'strands-agents[ollama]'``.
"""
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"


def get_model() -> Any:
    """Build the Strands model used by every agent from environment variables.

    **STRANDS_MODEL_PROVIDER** — ``openai`` (default) or ``ollama``.

    **OpenAI:** ``OPENAI_API_KEY``, optional ``OPENAI_BASE_URL``, ``OPENAI_MODEL_ID``
    (default ``gpt-4.1-nano``).

    **Ollama:** ``OLLAMA_HOST`` (default ``http://localhost:11434``), ``OLLAMA_MODEL_ID``
    (default ``llama3.1``). Optional: ``OLLAMA_TEMPERATURE``, ``OLLAMA_TOP_P``,
    ``OLLAMA_MAX_TOKENS``, ``OLLAMA_KEEP_ALIVE`` (e.g. ``5m``, ``10m``).
    """
    provider = (os.getenv("STRANDS_MODEL_PROVIDER") or PROVIDER_OPENAI).strip().lower()

    if provider == PROVIDER_OLLAMA:
        from strands.models.ollama import OllamaModel

        host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").strip()
        if not host:
            host = "http://localhost:11434"
        kwargs: dict[str, Any] = {
            "host": host,
            "model_id": os.getenv("OLLAMA_MODEL_ID", "llama3.1"),
        }
        temp = os.getenv("OLLAMA_TEMPERATURE", "").strip()
        if temp != "":
            kwargs["temperature"] = float(temp)
        top_p = os.getenv("OLLAMA_TOP_P", "").strip()
        if top_p != "":
            kwargs["top_p"] = float(top_p)
        max_tokens = os.getenv("OLLAMA_MAX_TOKENS", "").strip()
        if max_tokens != "":
            kwargs["max_tokens"] = int(max_tokens)
        keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "").strip()
        if keep_alive != "":
            kwargs["keep_alive"] = keep_alive
        return OllamaModel(**kwargs)

    if provider != PROVIDER_OPENAI:
        raise ValueError(
            f"Unknown STRANDS_MODEL_PROVIDER={provider!r}; use {PROVIDER_OPENAI!r} or {PROVIDER_OLLAMA!r}."
        )

    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        },
        model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4.1-nano"),
    )
