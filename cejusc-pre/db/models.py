"""
Modelos SQLAlchemy — tabelas do banco de dados.

Cada tabela corresponde a uma entidade do sistema CEJUSC pre-processual.
UUIDs como chave primaria em todas as tabelas.
Colunas JSON para dados aninhados (reclamante, reclamado, pedidos, condicoes, payload).
Timestamps em UTC.

Principio: append-only no EventoLog — nenhum evento e deletado ou editado.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from db.database import Base


def _uuid_str() -> str:
    """Gera UUID como string para usar como default em colunas."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Retorna datetime UTC atual."""
    return datetime.now(UTC)


# ══════════════════════════════════════════════════════════════════════════
# EventoLog — append-only event log (Event Sourcing)
# ══════════════════════════════════════════════════════════════════════════

class EventoLog(Base):
    """
    Log imutavel de eventos processuais — append-only.

    Cada registro e um 'commit' no historico do processo.
    O hash encadeia eventos anteriores (integridade tipo blockchain).
    Nenhum registro e editado ou deletado — apenas append.
    """
    __tablename__ = "evento_log"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    processo_id = Column(String(36), nullable=False, index=True)
    estado_anterior = Column(String(50), nullable=False, default="")
    estado_novo = Column(String(50), nullable=False)
    ator_id = Column(String(100), nullable=False)
    ator_tipo = Column(String(30), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    payload = Column(JSON, nullable=False, default=dict)
    hash_anterior = Column(String(64), nullable=False, default="")
    hash = Column(String(64), nullable=False, default="")

    def __repr__(self) -> str:
        return (
            f"<EventoLog {self.id[:8]}... "
            f"{self.estado_anterior} -> {self.estado_novo}>"
        )


# ══════════════════════════════════════════════════════════════════════════
# ReclamacaoDB — reclamacoes pre-processuais
# ══════════════════════════════════════════════════════════════════════════

class ReclamacaoDB(Base):
    """
    Reclamacao pre-processual — art. 9o Res. 403/2023.

    Campos aninhados (reclamante, reclamado, pedidos) armazenados como JSON
    para manter flexibilidade do MVP sem necessidade de joins complexos.
    Em producao: normalizar em tabelas separadas.
    """
    __tablename__ = "reclamacoes"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    cejusc_destino = Column(String(200), nullable=False)
    reclamante = Column(JSON, nullable=False)
    reclamado = Column(JSON, nullable=False)
    fatos = Column(Text, nullable=False)
    pedidos = Column(JSON, nullable=False)
    valor_causa = Column(String(20), nullable=False)
    modalidade = Column(String(20), nullable=False)
    opcao_custas = Column(String(30), nullable=False)
    estado_atual = Column(String(50), nullable=False, default="SOLICITACAO_RECEBIDA")
    protocolado_em = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relacionamentos
    sessoes = relationship("SessaoDB", back_populates="reclamacao")
    acordos = relationship("AcordoDB", back_populates="reclamacao")

    def __repr__(self) -> str:
        return f"<ReclamacaoDB {self.id[:8]}... estado={self.estado_atual}>"


# ══════════════════════════════════════════════════════════════════════════
# SessaoDB — sessoes de conciliacao/mediacao
# ══════════════════════════════════════════════════════════════════════════

class SessaoDB(Base):
    """
    Sessao de conciliacao/mediacao — art. 11-14 Res. 403/2023.

    Cada sessao e vinculada a uma reclamacao.
    Continuacoes sao novas sessoes com numero_sessao incrementado.
    """
    __tablename__ = "sessoes"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    reclamacao_id = Column(
        String(36),
        ForeignKey("reclamacoes.id"),
        nullable=False,
        index=True,
    )
    conciliador_id = Column(String(100), nullable=False)
    conciliador_nome = Column(String(200), nullable=False)
    data_agendada = Column(String(50), nullable=False)  # ISO8601 string
    numero_sessao = Column(Integer, nullable=False, default=1)
    resultado = Column(String(30), nullable=True)
    ata_conteudo = Column(Text, nullable=True)
    criada_em = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relacionamentos
    reclamacao = relationship("ReclamacaoDB", back_populates="sessoes")
    acordos = relationship("AcordoDB", back_populates="sessao")

    def __repr__(self) -> str:
        return f"<SessaoDB {self.id[:8]}... sessao #{self.numero_sessao}>"


# ══════════════════════════════════════════════════════════════════════════
# AcordoDB — acordos + parecer MP + homologacao
# ══════════════════════════════════════════════════════════════════════════

class AcordoDB(Base):
    """
    Acordo obtido em sessao — art. 13 Res. 403/2023.

    Condicoes e parecer_mp armazenados como JSON.
    Status: REDIGIDO -> PARECER_MP_EMITIDO (se menores) -> HOMOLOGADO.
    """
    __tablename__ = "acordos"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    reclamacao_id = Column(
        String(36),
        ForeignKey("reclamacoes.id"),
        nullable=False,
        index=True,
    )
    sessao_id = Column(
        String(36),
        ForeignKey("sessoes.id"),
        nullable=False,
    )
    condicoes = Column(JSON, nullable=False, default=list)
    envolve_menores_incapazes = Column(Boolean, nullable=False, default=False)
    status = Column(String(30), nullable=False, default="REDIGIDO")
    valor_total = Column(String(20), nullable=False, default="0")
    pode_homologar = Column(Boolean, nullable=False, default=True)
    parecer_mp = Column(JSON, nullable=True)
    redigido_em = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relacionamentos
    reclamacao = relationship("ReclamacaoDB", back_populates="acordos")
    sessao = relationship("SessaoDB", back_populates="acordos")

    def __repr__(self) -> str:
        return f"<AcordoDB {self.id[:8]}... status={self.status}>"


# ══════════════════════════════════════════════════════════════════════════
# UsuarioDB — usuarios do sistema
# ══════════════════════════════════════════════════════════════════════════

class UsuarioDB(Base):
    """
    Usuario do sistema — autenticacao e autorizacao.

    Perfis: PARTE, ADVOGADO, CONCILIADOR, MEDIADOR,
            SECRETARIA, JUIZ_COORDENADOR, MP.
    """
    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=_uuid_str)
    nome = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False, unique=True, index=True)
    senha_hash = Column(String(200), nullable=False)
    perfil = Column(String(30), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    def __repr__(self) -> str:
        return f"<UsuarioDB {self.email} perfil={self.perfil}>"
