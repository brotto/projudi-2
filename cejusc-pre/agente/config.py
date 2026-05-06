"""
Agent configuration — loaded from environment variables.

Single source of truth for endpoints, models, and feature flags.
Defaults assume the EasyPanel `privateai` project (production).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class AgentConfig:
    # ── LLM (Ollama) ──────────────────────────────────────────────────────
    # Inside privateai project: http://privateai_ollama:11434
    # From outside the project: https://privateai-ollama.74udkv.easypanel.host
    ollama_url: str = _env("JUIZO_OLLAMA_URL", "https://privateai-ollama.74udkv.easypanel.host")
    model_extractor: str = _env("JUIZO_MODEL_EXTRATOR", "qwen-extrator")
    model_analyzer: str = _env("JUIZO_MODEL_JURIDICO", "qwen-juridico")
    model_drafter: str = _env("JUIZO_MODEL_REDATOR", "qwen-redator")
    model_embed: str = _env("JUIZO_MODEL_EMBED", "nomic-embed-text")

    # ── Vector store (Qdrant) ─────────────────────────────────────────────
    qdrant_url: str = _env("JUIZO_QDRANT_URL", "https://vector.brotto.io")
    qdrant_collection: str = _env("JUIZO_QDRANT_COLLECTION", "cejusc-pre")

    # ── RAG ───────────────────────────────────────────────────────────────
    rag_top_k: int = int(_env("JUIZO_RAG_TOP_K", "6"))
    chunk_min_words: int = int(_env("JUIZO_CHUNK_MIN_WORDS", "50"))
    chunk_max_words: int = int(_env("JUIZO_CHUNK_MAX_WORDS", "400"))

    # ── Vault ─────────────────────────────────────────────────────────────
    vault_path: str = _env(
        "JUIZO_VAULT_PATH",
        "/Users/alebrotto/Documents/CEJUSC Pre Vault",
    )

    # ── Provider switch (preparado para futuro — POC só tem ollama) ──────
    llm_provider: str = _env("JUIZO_LLM_PROVIDER", "ollama")


CONFIG = AgentConfig()
