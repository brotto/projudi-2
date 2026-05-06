"""Modelos base do sistema Juízo — objetos estruturados validáveis."""

from juizo.models.base import EventoProcessual, TipoAtor
from juizo.models.partes import Advogado, Endereco, Parte, TipoPessoa, UF
from juizo.models.pedidos import Fundamento, Pedido
from juizo.models.processo import Processo, Rito

__all__ = [
    "Advogado",
    "Endereco",
    "EventoProcessual",
    "Fundamento",
    "Parte",
    "Pedido",
    "Processo",
    "Rito",
    "TipoAtor",
    "TipoPessoa",
    "UF",
]
