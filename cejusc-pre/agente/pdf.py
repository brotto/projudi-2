"""
PDF text extraction for the agent.

Uses pdfplumber for robust text extraction. Truncates to a safe size so the
analyzer doesn't blow past Qwen's context window with the RAG context attached.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pdfplumber


# Qwen2.5-14B has a 128K context. We leave generous headroom for:
#   ~6K chars  RAG context (top-6 chunks × ~1K)
#   ~2K chars  system prompt
#   ~3K chars  question + chat history
# So budget ~80K chars (≈ 20K tokens) for the PDF body itself.
MAX_PDF_CHARS = 80_000


def extract_text(source: str | Path | IO[bytes]) -> str:
    """Return concatenated text from all pages of the PDF."""
    pieces: list[str] = []
    with pdfplumber.open(source) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            txt = page.extract_text() or ""
            if not txt.strip():
                continue
            pieces.append(f"\n\n--- página {i} ---\n{txt}")
    full = "".join(pieces).strip()
    if len(full) > MAX_PDF_CHARS:
        # Strategy: keep the first ~20K (capa, partes, primeiros movimentos)
        # and the last ~60K (atos finais, sentença, decisões) — descarta meio.
        head = full[:20_000]
        tail = full[-60_000:]
        full = (
            head
            + "\n\n[... trecho do meio omitido para caber no contexto ...]\n\n"
            + tail
        )
    return full
