"""
Engine FSM configurada para o rito sumarissimo — Juizados Especiais Civeis.

Instancia o FSMEngine generico do juizo-core com os estados,
transicoes, permissoes e atos automaticos da Lei 9.099/95.
"""

from __future__ import annotations

from juizo.fsm.base import RitoFSM
from juizo.fsm.engine import FSMEngine

from fsm.estados import (
    ESTADOS_TERMINAIS,
    PERMISSOES,
    TRANSICOES,
)


class JECRitoFSM(RitoFSM):
    """
    Definicao FSM do rito sumarissimo — Juizados Especiais Civeis.
    Base legal: Lei 9.099/95.
    """

    @property
    def transicoes(self) -> dict[str, list[str]]:
        return TRANSICOES

    @property
    def estados_terminais(self) -> set[str]:
        return ESTADOS_TERMINAIS

    @property
    def permissoes(self) -> dict[str, list[str]]:
        return PERMISSOES


# Instancia singleton — usada pela API e pelos testes
jec_fsm = JECRitoFSM()
engine = jec_fsm.criar_engine()
