"""
Classe base abstrata para definição de FSMs por rito processual.

Cada rito processual (CEJUSC-PRÉ, rito ordinário, penal, etc.)
subclasse RitoFSM para declarar seus estados, transições,
permissões e atos automáticos. O motor FSM é instanciado
automaticamente a partir desta configuração.

Uso:
    class CejuscPreFSM(RitoFSM):
        @property
        def transicoes(self) -> dict[str, list[str]]:
            return TRANSICOES

        @property
        def estados_terminais(self) -> set[str]:
            return ESTADOS_TERMINAIS

    fsm = CejuscPreFSM()
    engine = fsm.criar_engine()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from juizo.fsm.engine import FSMEngine


class RitoFSM(ABC):
    """
    Classe base para definição de FSMs por rito processual.

    Cada rito subclasse RitoFSM e define:
    - transicoes: mapa estado -> [estados_destino]
    - estados_terminais: estados frozen (sem saída)
    - permissoes (opcional): estado_destino -> [tipos_ator]
    - atos_automaticos (opcional): (origem, destino) -> [callable]
    """

    @property
    @abstractmethod
    def transicoes(self) -> dict[str, list[str]]:
        """Mapa de transições válidas: estado_atual -> [estados_destino]."""
        ...

    @property
    @abstractmethod
    def estados_terminais(self) -> set[str]:
        """Conjunto de estados terminais (frozen — sem transições de saída)."""
        ...

    @property
    def permissoes(self) -> dict[str, list[str]]:
        """Mapa de permissões: estado_destino -> [tipos_ator_permitidos]."""
        return {}

    @property
    def atos_automaticos(self) -> dict[tuple[str, str], list[Callable[..., Any]]]:
        """Mapa de atos automáticos: (estado_origem, estado_destino) -> [callable]."""
        return {}

    def criar_engine(self) -> FSMEngine:
        """Cria uma instância do FSMEngine configurada para este rito."""
        return FSMEngine(
            transicoes=self.transicoes,
            estados_terminais=self.estados_terminais,
            permissoes=self.permissoes,
            atos_automaticos=self.atos_automaticos,
        )

    def validar_definicao(self) -> list[str]:
        """
        Valida a consistência da definição do rito.

        Verifica:
        - Estados terminais devem ter lista de transições vazia
        - Todo estado destino em transições deve estar definido como chave
        - Permissões referenciam apenas estados existentes

        Returns:
            Lista de erros encontrados (vazia = definição válida).
        """
        erros: list[str] = []

        # Todos os estados conhecidos
        todos_estados = set(self.transicoes.keys())

        # Terminais devem ter transições vazias
        for terminal in self.estados_terminais:
            transicoes = self.transicoes.get(terminal, [])
            if transicoes:
                erros.append(
                    f"Estado terminal '{terminal}' tem transições de saída: {transicoes}"
                )

        # Todo estado destino deve existir como chave
        for origem, destinos in self.transicoes.items():
            for destino in destinos:
                if destino not in todos_estados:
                    erros.append(
                        f"Estado destino '{destino}' (de '{origem}') "
                        f"não está definido no mapa de transições"
                    )

        # Permissões referenciam apenas estados existentes
        for estado in self.permissoes:
            if estado not in todos_estados:
                erros.append(
                    f"Permissão definida para estado '{estado}' "
                    f"que não existe no mapa de transições"
                )

        return erros
