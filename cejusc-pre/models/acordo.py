"""
Modelos de acordo — CEJUSC pré-processual.

art. 13 §3º / art. 15–16 · Res. 403/2023:
- Acordo redigido pelas partes com auxílio do conciliador/mediador
- Menores/incapazes: MP obrigatório antes da homologação (art. 15 §ú)
- Homologação pelo juiz coordenador (art. 15)
- Título executivo judicial após homologação (art. 16)
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class StatusAcordo(str, Enum):
    """Status do acordo no fluxo de homologação."""
    REDIGIDO = "REDIGIDO"
    AGUARDANDO_MP = "AGUARDANDO_MP"
    PARECER_MP_EMITIDO = "PARECER_MP_EMITIDO"
    CONCLUSO_JUIZ = "CONCLUSO_JUIZ"
    HOMOLOGADO = "HOMOLOGADO"


class CondicaoAcordo(BaseModel):
    """
    Condição específica do acordo — obrigação assumida por uma das partes.

    Cada condição é um objeto estruturado com:
    - Descrição da obrigação
    - Parte responsável
    - Valor (quando aplicável)
    - Prazo de cumprimento
    """
    descricao: str = Field(min_length=5)
    parte_responsavel: str = Field(min_length=2)  # nome da parte
    valor: Decimal | None = None
    prazo_cumprimento: datetime | None = None
    forma_pagamento: str = ""

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Valor da condição não pode ser negativo")
        return v


class ParecerMP(BaseModel):
    """
    Parecer do Ministério Público — art. 15 §ú.

    Obrigatório quando houver menores ou incapazes envolvidos.
    """
    id: UUID = Field(default_factory=uuid4)
    acordo_id: UUID
    promotor_id: UUID
    promotor_nome: str = Field(min_length=2)
    favoravel: bool
    fundamentacao: str = Field(min_length=10)
    emitido_em: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AcordoCejusc(BaseModel):
    """
    Acordo pré-processual — CEJUSC · Res. 403/2023.

    art. 13 §3º — acordo redigido com condições específicas.
    art. 15 — homologado pelo juiz coordenador.
    art. 16 — constitui título executivo judicial.
    """
    id: UUID = Field(default_factory=uuid4)
    reclamacao_id: UUID
    sessao_id: UUID  # sessão em que o acordo foi obtido

    # Conteúdo do acordo
    condicoes: list[CondicaoAcordo] = Field(min_length=1)

    # Partes envolvem menores/incapazes? (art. 15 §ú — MP obrigatório)
    envolve_menores_incapazes: bool = False

    # Status no fluxo de homologação
    status: StatusAcordo = StatusAcordo.REDIGIDO

    # Parecer MP (quando aplicável)
    parecer_mp: ParecerMP | None = None

    # Homologação
    homologado_por_id: UUID | None = None
    homologado_por_nome: str = ""
    homologado_em: datetime | None = None

    # Metadados
    redigido_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def requer_mp(self) -> bool:
        """art. 15 §ú — acordo com menores/incapazes requer parecer do MP."""
        return self.envolve_menores_incapazes

    def pode_homologar(self) -> bool:
        """
        Verifica se o acordo está pronto para homologação pelo juiz.

        - Se envolve menores/incapazes: precisa de parecer favorável do MP
        - Caso contrário: pode ir direto ao juiz
        """
        if self.envolve_menores_incapazes:
            return (
                self.parecer_mp is not None
                and self.parecer_mp.favoravel
            )
        return True

    @property
    def valor_total(self) -> Decimal:
        """Soma dos valores de todas as condições do acordo."""
        return sum(
            (c.valor for c in self.condicoes if c.valor is not None),
            Decimal("0"),
        )
