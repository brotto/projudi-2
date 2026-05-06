"""
Modelos base de processo judicial.

Define os tipos fundamentais:
- Rito: classificação do rito processual
- Processo: container principal do processo com estado FSM
"""

from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Rito(str, Enum):
    """Ritos processuais suportados pelo sistema."""
    CEJUSC_PRE = "CEJUSC_PRE"
    # Futuros ritos:
    # RITO_SUMARISSIMO = "RITO_SUMARISSIMO"
    # RITO_ORDINARIO = "RITO_ORDINARIO"
    # RITO_PENAL = "RITO_PENAL"
    # EXECUCAO = "EXECUCAO"


class Processo(BaseModel):
    """
    Container principal do processo judicial.

    O processo é um repositório Git:
    - main branch = fluxo principal
    - branches = incidentes processuais
    - commits = eventos processuais (append-only)
    - tag v1.0.0 = trânsito em julgado

    O estado atual é sempre derivado do log de eventos (Event Sourcing).
    """
    id: UUID = Field(default_factory=uuid4)
    numero: str | None = None  # gerado pelo sistema na fase CADASTRADO
    rito: Rito
    estado_atual: str
    criado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Metadados
    comarca: str = ""
    vara: str = ""
    unidade: str = ""  # ex: "CEJUSC-CENTRAL-CURITIBA"
