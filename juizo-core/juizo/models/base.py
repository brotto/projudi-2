"""
Modelos base do sistema Juízo.

Define os tipos fundamentais reutilizáveis por qualquer rito processual:
- TipoAtor: classificação de atores processuais
- EventoProcessual: entrada imutável no log append-only
"""

from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
import hashlib
import json

from pydantic import BaseModel, Field, ConfigDict


class TipoAtor(str, Enum):
    """Tipos de atores processuais reconhecidos pelo sistema."""
    PARTE = "PARTE"
    ADVOGADO = "ADVOGADO"
    SECRETARIA = "SECRETARIA"
    JUIZ_COORDENADOR = "JUIZ_COORDENADOR"
    CONCILIADOR = "CONCILIADOR"
    MEDIADOR = "MEDIADOR"
    MP = "MP"


class EventoProcessual(BaseModel):
    """
    Entrada imutável no log append-only do processo.

    Análogo a um commit Git — cada evento é encadeado por hash SHA-256,
    formando um DAG (Directed Acyclic Graph) auditável.

    Nenhum evento é editado ou deletado. O estado atual de qualquer processo
    é sempre derivado da replay do log de eventos (Event Sourcing — ADR-001).
    """
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    tipo: str
    processo_id: UUID
    ator_id: UUID
    ator_tipo: TipoAtor
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    hash_anterior: str = ""
    assinatura: str = ""

    @property
    def hash(self) -> str:
        """Hash SHA-256 do evento — identidade criptográfica imutável."""
        conteudo = json.dumps({
            "id": str(self.id),
            "tipo": self.tipo,
            "processo_id": str(self.processo_id),
            "ator_id": str(self.ator_id),
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "hash_anterior": self.hash_anterior,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(conteudo.encode()).hexdigest()
