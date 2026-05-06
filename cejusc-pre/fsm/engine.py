"""
Engine FSM configurada para o rito CEJUSC pré-processual.

Instancia o FSMEngine genérico do juizo-core com os estados,
transições, permissões e atos automáticos da Res. 403/2023.
"""

from __future__ import annotations

from juizo.fsm.base import RitoFSM
from juizo.fsm.engine import FSMEngine

from fsm.estados import (
    ESTADOS_TERMINAIS,
    PERMISSOES,
    TRANSICOES,
)


class CejuscPreFSM(RitoFSM):
    """
    Definição FSM do procedimento pré-processual CEJUSC.
    Base legal: Res. 403/2023 · NUPEMEC · TJPR.
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


# Instância singleton — usada pela API e pelos testes
cejusc_pre_fsm = CejuscPreFSM()
engine = cejusc_pre_fsm.criar_engine()
