"""
FastAPI app — CEJUSC pré-processual · Res. 403/2023.

Sistema de Informação Jurisdicional — MVP.
O processo judicial é informação estruturada, não PDFs.

Endpoints:
- /auth — registro, login, consulta de usuario autenticado
- /reclamacoes — CRUD + transições FSM + histórico
- /sessoes — agendamento e resultado de sessões
- /acordos — registro, parecer MP, homologação
- /automacoes — carta-convite, certidão negativa, prazos
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, UTC
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Garante que cejusc-pre/ está no sys.path para imports locais
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.routes.reclamacoes import router as reclamacoes_router
from api.routes.sessoes import router as sessoes_router
from api.routes.acordos import router as acordos_router
from api.routes.auth import router as auth_router
from api.deps import get_store, USE_SQL
from api.schemas import CartaConviteOut, CertidaoNegativaOut, PrazosOut
from api.store import EventStore

from servicos.automacoes import (
    gerar_carta_convite,
    gerar_certidao_negativa,
    calcular_prazos,
)


# ══════════════════════════════════════════════════════════════════════════
# Lifespan — startup/shutdown
# ══════════════════════════════════════════════════════════════════════════

# Quando JUIZO_USE_SQL=true, cria as tabelas no banco no startup.
# Em producao: usar Alembic para migrations ao inves de create_tables().

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializacao e encerramento da aplicacao."""
    # Startup: criar tabelas se USE_SQL ativo
    if USE_SQL:
        from db.database import create_tables
        create_tables()
    yield
    # Shutdown: nada a fazer no MVP


# ══════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Juízo · CEJUSC Pré-Processual",
    description=(
        "Sistema de Informação Jurisdicional — MVP\n\n"
        "**Base legal:** Resolução 403/2023 · NUPEMEC · TJPR\n\n"
        "O processo judicial é informação estruturada.\n"
        "Event Sourcing + FSM por rito + append-only log imutável."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP — restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handlers ──

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler global — garante respostas JSON mesmo em erros inesperados."""
    return JSONResponse(
        status_code=500,
        content={
            "status": "ERRO_INTERNO",
            "mensagem": str(exc),
        },
    )


# ── Routers ──

app.include_router(auth_router, prefix="/api/v1")
app.include_router(reclamacoes_router, prefix="/api/v1")
app.include_router(sessoes_router, prefix="/api/v1")
app.include_router(acordos_router, prefix="/api/v1")


# ══════════════════════════════════════════════════════════════════════════
# Automações (Fase 4)
# ══════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/v1/automacoes/{reclamacao_id}/carta-convite",
    response_model=CartaConviteOut,
    tags=["Automações"],
    summary="Gerar carta-convite — art. 10º III/IV",
)
def gerar_carta_convite_endpoint(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> CartaConviteOut:
    """
    Gera automaticamente a carta-convite ao reclamado.

    art. 10º III/IV — Notificação do reclamado para comparecer
    à sessão de conciliação/mediação.
    """
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    carta = gerar_carta_convite(rec)
    return CartaConviteOut(**carta)


@app.get(
    "/api/v1/automacoes/{reclamacao_id}/certidao-negativa",
    response_model=CertidaoNegativaOut,
    tags=["Automações"],
    summary="Gerar certidão negativa — art. 12 §3º",
)
def gerar_certidao_negativa_endpoint(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> CertidaoNegativaOut:
    """
    Gera automaticamente a certidão negativa de conciliação.

    art. 12 §3º — Emitida quando a sessão é infrutífera.
    art. 4º — Certifica que o procedimento não induz prevenção,
    não interrompe prescrição, não constitui em mora.
    """
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    certidao = gerar_certidao_negativa(rec)
    return CertidaoNegativaOut(**certidao)


@app.get(
    "/api/v1/automacoes/{reclamacao_id}/prazos",
    response_model=PrazosOut,
    tags=["Automações"],
    summary="Calcular prazos legais — art. 9º §2º, art. 14",
)
def calcular_prazos_endpoint(
    reclamacao_id: UUID,
    store: EventStore = Depends(get_store),
) -> PrazosOut:
    """
    Calcula prazos legais da reclamação.

    Prazos computados:
    - Regularização: 5 dias (art. 9º §2º)
    - Máx. sem sessão: 30 dias (art. 14)
    - Máx. com continuação: 60 dias (art. 14)
    """
    rec = store.get_reclamacao(reclamacao_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reclamação {reclamacao_id} não encontrada",
        )

    # Pegar data de protocolo do primeiro evento
    historico = store.get_historico(reclamacao_id)
    data_protocolo = None
    if historico:
        data_protocolo = datetime.fromisoformat(historico[0]["timestamp"])

    prazos = calcular_prazos(rec, data_protocolo=data_protocolo)
    return PrazosOut(**prazos)


# ══════════════════════════════════════════════════════════════════════════
# Health check
# ══════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Sistema"])
def root():
    """Health check — informações sobre o sistema."""
    return {
        "sistema": "Juízo · Sistema de Informação Jurisdicional",
        "modulo": "CEJUSC Pré-Processual",
        "versao": "0.1.0",
        "base_legal": "Res. 403/2023 · NUPEMEC · TJPR",
        "filosofia": "O processo judicial é informação estruturada, não PDFs.",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/api/v1/saude", tags=["Sistema"])
def saude(store: EventStore = Depends(get_store)):
    """Status da API e contadores."""
    return {
        "status": "operacional",
        "timestamp": datetime.now(UTC).isoformat(),
        "contadores": {
            "reclamacoes": len(store._reclamacoes),
            "sessoes": len(store._sessoes),
            "acordos": len(store._acordos),
        },
    }
