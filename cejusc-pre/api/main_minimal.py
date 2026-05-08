"""
API mínima — apenas /health e /agent/* — para diagnóstico de container no EasyPanel.

Bypassa imports pesados (passlib, psycopg, jwt, sqlmodel) que podem ter
incompatibilidade de wheel entre macOS e Linux do container.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

# sys.path setup (igual ao main.py original)
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from api.routes.agent import router as agent_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sem migrations, sem DB. Só sobe o servidor.
    print("[main_minimal] startup OK", flush=True)
    yield
    print("[main_minimal] shutdown", flush=True)


app = FastAPI(
    title="Sistema Juízo · CEJUSC Pré (minimal)",
    description="API mínima para diagnóstico — apenas agent endpoints.",
    version="0.0.1-minimal",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    return {
        "status": "ok",
        "service": "cejusc-pre-agent",
        "mode": "minimal",
        "version": "0.0.1",
    }


# Mesmo prefix do main.py original pra Worker bater no path certo
app.include_router(agent_router, prefix="/api/v1")
