"""
Rotas REST do Agente IA — CEJUSC pré-processual.

Endpoints:
- POST /agent/analyze — análise + drafting com PDF opcional
- GET  /agent/health  — healthcheck simples (modelo, qdrant, ollama)

Autenticação:
- Header `X-Agent-Token` deve bater com env `AGENT_INTERNAL_TOKEN`.
- Esse token é compartilhado entre o Cloudflare Worker (Projeto-CEJUSC-2.0)
  e este serviço — o Worker faz autenticação do usuário (admin/estagiario)
  e proxia a chamada com o token interno.
"""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from agente.analyzer import analyze
from agente.config import CONFIG
from agente.pdf import extract_text


router = APIRouter(prefix="/agent", tags=["agent"])


# ─── Pydantic models ────────────────────────────────────────────────────────


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    pdf_b64: str | None = Field(
        default=None,
        description="PDF do processo em base64. Opcional. Limite: ~25MB encodado.",
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        description="Mensagens anteriores da conversa para continuidade. Últimas 6 são usadas.",
    )


class Source(BaseModel):
    path: str
    section: str | None = None
    score: float | None = None
    type: str | None = None


class AnalyzeResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    elapsed_ms: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    model_analyzer: str
    qdrant_url: str
    qdrant_collection: str
    ollama_url: str
    vault_path: str


# ─── Auth dependency ─────────────────────────────────────────────────────────


def _check_token(x_agent_token: str | None) -> None:
    expected = os.getenv("AGENT_INTERNAL_TOKEN", "").strip()
    if not expected:
        # Sem token configurado, recusamos por segurança em produção.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AGENT_INTERNAL_TOKEN não configurado no servidor.",
        )
    if not x_agent_token or x_agent_token.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token interno inválido ou ausente.",
        )


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Healthcheck público — não exige token; útil para load balancer/uptime."""
    return HealthResponse(
        status="ok",
        model_analyzer=CONFIG.model_analyzer,
        qdrant_url=CONFIG.qdrant_url,
        qdrant_collection=CONFIG.qdrant_collection,
        ollama_url=CONFIG.ollama_url,
        vault_path=CONFIG.vault_path,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    body: AnalyzeRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> AnalyzeResponse:
    """Pipeline completo: PDF (opcional) + RAG + LLM (OpenRouter)."""
    _check_token(x_agent_token)

    # PDF: decodificar base64 → texto
    pdf_text: str | None = None
    if body.pdf_b64:
        try:
            raw = base64.b64decode(body.pdf_b64, validate=True)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF base64 inválido: {e}",
            )
        try:
            pdf_text = extract_text(io.BytesIO(raw))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Falha ao extrair texto do PDF: {e}",
            )

    history = [m.model_dump() for m in body.history]

    t0 = time.time()
    try:
        result = await analyze(
            body.question,
            pdf_text=pdf_text,
            history=history,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha no pipeline do agente: {e}",
        )
    elapsed_ms = int((time.time() - t0) * 1000)

    return AnalyzeResponse(
        answer=result.answer,
        sources=[Source(**s) for s in result.sources],
        model=result.model,
        elapsed_ms=elapsed_ms,
    )
