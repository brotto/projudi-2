"""FSM — Motor de máquina de estados para ritos processuais."""

from juizo.fsm.base import RitoFSM
from juizo.fsm.engine import EventoTransicao, FSMEngine, ResultadoValidacao

__all__ = [
    "EventoTransicao",
    "FSMEngine",
    "ResultadoValidacao",
    "RitoFSM",
]
