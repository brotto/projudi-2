"""
Exceções do sistema Juízo.

Toda exceção deve ser descritiva e incluir o contexto exato do erro —
o usuário (advogado, parte, serventuário) recebe a mensagem diretamente.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ErroValidacao:
    """Erro de validação de um campo específico."""
    campo: str
    mensagem: str
    valor_recebido: Any = None


class ErroProtocolo(Exception):
    """
    Levantada quando um ato processual não passa na validação antes do protocolo.
    Lista exata de todos os campos com problema.
    """
    def __init__(self, erros: list[ErroValidacao]) -> None:
        self.erros = erros
        msgs = "; ".join(f"{e.campo}: {e.mensagem}" for e in erros)
        super().__init__(f"Erro de protocolo: {msgs}")


class TransicaoInvalida(Exception):
    """
    Levantada quando se tenta executar uma transição de estado não permitida.
    Inclui o estado atual e as transições válidas disponíveis.
    """
    def __init__(
        self,
        estado_atual: str,
        transicao_tentada: str,
        transicoes_validas: list[str],
    ) -> None:
        self.estado_atual = estado_atual
        self.transicao_tentada = transicao_tentada
        self.transicoes_validas = transicoes_validas
        super().__init__(
            f"Transição inválida: '{transicao_tentada}' não é permitida "
            f"a partir de '{estado_atual}'. "
            f"Transições válidas: {transicoes_validas}"
        )


class AtorNaoAutorizado(Exception):
    """
    Levantada quando um ator tenta executar um ato para o qual não tem permissão
    no estado atual do processo.
    """
    def __init__(self, ator_tipo: str, ato: str, estado: str) -> None:
        self.ator_tipo = ator_tipo
        self.ato = ato
        self.estado = estado
        super().__init__(
            f"Ator '{ator_tipo}' não está autorizado a executar '{ato}' "
            f"no estado '{estado}'"
        )


class EstadoTerminal(Exception):
    """
    Levantada quando se tenta modificar um processo em estado terminal (frozen).
    Estados terminais são imutáveis por design.
    """
    def __init__(self, estado: str) -> None:
        self.estado = estado
        super().__init__(
            f"Processo em estado terminal '{estado}' — imutável por design. "
            f"Nenhuma transição é possível a partir de um estado terminal."
        )


class PrazoExpirado(Exception):
    """
    Levantada quando uma ação é tentada após o prazo legal.
    """
    def __init__(self, prazo_tipo: str, prazo_dias: int, artigo: str) -> None:
        self.prazo_tipo = prazo_tipo
        self.prazo_dias = prazo_dias
        self.artigo = artigo
        super().__init__(
            f"Prazo expirado: '{prazo_tipo}' — {prazo_dias} dias ({artigo})"
        )


class AssinaturaInsuficiente(Exception):
    """
    Levantada quando a assinatura convergente nao atinge o score minimo
    exigido para o ato processual.
    """
    def __init__(
        self,
        score_obtido: float,
        score_exigido: float,
        sinais_ausentes: list[str] | None = None,
        motivo: str = "",
    ) -> None:
        self.score_obtido = score_obtido
        self.score_exigido = score_exigido
        self.sinais_ausentes = sinais_ausentes or []
        self.motivo = motivo
        super().__init__(
            f"Assinatura insuficiente: score {score_obtido:.2f} "
            f"(minimo {score_exigido:.2f}). {motivo}"
        )


class CompetenciaExcluida(Exception):
    """
    Levantada na triagem quando a matéria é excluída da competência do CEJUSC-PRÉ.
    """
    def __init__(self, motivo: str, artigo: str) -> None:
        self.motivo = motivo
        self.artigo = artigo
        super().__init__(
            f"Matéria excluída da competência: {motivo} ({artigo})"
        )
