"""
Configuracao do banco de dados SQLAlchemy — camada de persistencia.

MVP: SQLite para desenvolvimento local.
Producao: PostgreSQL (event log) + Redis (cache de estado FSM).

O banco armazena:
- EventoLog: log imutavel append-only (Event Sourcing)
- ReclamacaoDB: reclamacoes pre-processuais
- SessaoDB: sessoes de conciliacao/mediacao
- AcordoDB: acordos + parecer MP + homologacao
- UsuarioDB: usuarios do sistema
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


# ── URL do banco ──
# MVP: SQLite local. Em producao: variavel de ambiente JUIZO_DATABASE_URL
DATABASE_URL = os.getenv(
    "JUIZO_DATABASE_URL",
    "sqlite:///./juizo_cejusc.db",
)

# ── Engine ──
# check_same_thread=False necessario para SQLite com FastAPI (multi-thread)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # True para debug SQL
)

# ── SessionLocal ──
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── Base declarativa ──
class Base(DeclarativeBase):
    """Classe base para todos os modelos SQLAlchemy do projeto."""
    pass


# ── Dependencia FastAPI ──
def get_db() -> Session:
    """
    Dependencia FastAPI que fornece uma sessao do banco.

    Uso:
        @app.get("/")
        def endpoint(db: Session = Depends(get_db)):
            ...

    A sessao e fechada automaticamente apos o request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Cria todas as tabelas no banco de dados.

    Chamado no startup da aplicacao quando USE_SQL=true.
    Em producao: usar Alembic para migrations.
    """
    # Importa models para registrar as tabelas no Base.metadata
    import db.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def create_tables_with_engine(eng) -> None:
    """
    Cria todas as tabelas usando um engine especifico.

    Util para testes com banco em memoria.
    """
    import db.models  # noqa: F401
    Base.metadata.create_all(bind=eng)
