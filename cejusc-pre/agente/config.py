"""
Agent configuration — loaded from environment variables.

Single source of truth for endpoints, models, and feature flags.

Provider split (per ADR-008):
- Chat (extraction / analysis / drafting) → OpenRouter (frontier API)
- Embeddings (RAG) → Ollama nomic-embed-text on the privateai EasyPanel project
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class AgentConfig:
    # ── Chat (OpenRouter) ─────────────────────────────────────────────────
    # OpenAI-compatible gateway. The OPENROUTER_API_KEY env var is required.
    openrouter_url: str = _env("JUIZO_OPENROUTER_URL", "https://openrouter.ai/api/v1")
    model_extractor: str = _env("JUIZO_MODEL_EXTRACTOR", "openai/gpt-4o-mini")
    model_analyzer: str = _env("JUIZO_MODEL_ANALYZER", "openai/gpt-4o")
    model_drafter: str = _env("JUIZO_MODEL_DRAFTER", "openai/gpt-4o")
    model_compliance_reviewer: str = _env(
        "JUIZO_MODEL_COMPLIANCE", "anthropic/claude-3.5-haiku"
    )

    # ── Embeddings (Ollama) ───────────────────────────────────────────────
    # Inside privateai project: http://privateai_ollama:11434
    # From outside the project: https://privateai-ollama.74udkv.easypanel.host
    ollama_url: str = _env("JUIZO_OLLAMA_URL", "https://privateai-ollama.74udkv.easypanel.host")
    model_embed: str = _env("JUIZO_MODEL_EMBED", "nomic-embed-text")

    # ── Vector store (Qdrant) ─────────────────────────────────────────────
    qdrant_url: str = _env("JUIZO_QDRANT_URL", "https://vector.brotto.io")
    qdrant_collection: str = _env("JUIZO_QDRANT_COLLECTION", "cejusc-pre")

    # ── RAG ───────────────────────────────────────────────────────────────
    rag_top_k: int = int(_env("JUIZO_RAG_TOP_K", "10"))
    chunk_min_words: int = int(_env("JUIZO_CHUNK_MIN_WORDS", "50"))
    chunk_max_words: int = int(_env("JUIZO_CHUNK_MAX_WORDS", "400"))

    # ── Vault ─────────────────────────────────────────────────────────────
    vault_path: str = _env(
        "JUIZO_VAULT_PATH",
        "/Users/alebrotto/Documents/CEJUSC Pre Vault",
    )

    # ── Provider switch ───────────────────────────────────────────────────
    # "openrouter" (default, ADR-008) | "ollama" (fallback, ADR-005 archived)
    llm_provider: str = _env("JUIZO_LLM_PROVIDER", "openrouter")


CONFIG = AgentConfig()
