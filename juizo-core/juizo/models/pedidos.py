"""
Modelos base de pedidos processuais.

Define os tipos fundamentais de pedidos e fundamentos:
- Pedido: pretensão da parte com descrição e valor
- Fundamento: base legal ou fática do pedido
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Fundamento(BaseModel):
    """Base legal ou fática de um pedido."""
    tipo: str = Field(min_length=1)  # "LEGAL" ou "FATICO"
    descricao: str = Field(min_length=1)
    dispositivo_legal: str | None = None  # ex: "art. 186 CC"


class Pedido(BaseModel):
    """
    Pretensão da parte — objeto estruturado, não texto livre.

    Cada pedido deve ter descrição clara, valor (quando mensurável)
    e opcionalmente os fundamentos legais/fáticos.
    """
    descricao: str = Field(min_length=5)
    valor: Decimal = Field(ge=0)
    fundamentos: list[Fundamento] = Field(default_factory=list)

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Valor do pedido não pode ser negativo")
        return v
