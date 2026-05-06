"""
Testes da FSM dos Juizados Especiais Civeis — cobertura 100% de estados e transicoes.

Testa:
- Todas as transicoes validas da Lei 9.099/95
- Rejeicao de transicoes invalidas
- Estados terminais (frozen)
- Permissoes por ator
- Prazos legais
- Materias excluidas da competencia
- Consistencia da definicao FSM
"""

from __future__ import annotations

import pytest

from juizo.exceptions import AtorNaoAutorizado, EstadoTerminal, TransicaoInvalida

from fsm.engine import jec_fsm, engine
from fsm.estados import (
    ESTADOS_TERMINAIS,
    EstadoJEC,
    LIMITE_SEM_ADVOGADO,
    MATERIAS_EXCLUIDAS,
    PERMISSOES,
    PRAZO_AUDIENCIA_CONCILIACAO,
    PRAZO_AUDIENCIA_INSTRUCAO,
    PRAZO_CITACAO,
    PRAZO_CUMPRIMENTO_SENTENCA,
    PRAZO_RECURSO,
    SALARIO_MINIMO,
    TRANSICOES,
    VALOR_MAXIMO_CAUSA,
)


# ======================================================================
# Validacao da definicao FSM
# ======================================================================

class TestDefinicaoFSM:
    """Verifica a consistencia da definicao da FSM."""

    def test_definicao_valida(self) -> None:
        erros = jec_fsm.validar_definicao()
        assert erros == [], f"Definicao FSM invalida: {erros}"

    def test_todos_estados_enum_presentes_em_transicoes(self) -> None:
        """Cada valor do Enum deve ter uma entrada no dict de transicoes."""
        for estado in EstadoJEC:
            assert estado in TRANSICOES, f"Estado {estado} ausente das transicoes"

    def test_todos_estados_terminais_sem_saida(self) -> None:
        for terminal in ESTADOS_TERMINAIS:
            assert TRANSICOES[terminal] == [], (
                f"Terminal {terminal} tem transicoes de saida"
            )

    def test_seis_estados_terminais(self) -> None:
        """6 estados terminais no rito sumarissimo."""
        assert len(ESTADOS_TERMINAIS) == 6

    def test_total_estados(self) -> None:
        """12 estados de fluxo + 6 terminais = 18."""
        assert len(EstadoJEC) == 18

    def test_todos_estados_tem_permissao(self) -> None:
        """Cada estado (exceto PETICAO_INICIAL) deve ter permissoes."""
        for estado in EstadoJEC:
            if estado == EstadoJEC.PETICAO_INICIAL:
                continue  # estado inicial — criado pelo protocolo da peticao
            assert estado in PERMISSOES, (
                f"Estado {estado} nao tem permissoes definidas"
            )


# ======================================================================
# Fluxo feliz — caminho peticao -> conciliacao -> acordo
# ======================================================================

class TestFluxoFelizAcordo:
    """Testa o caminho completo com acordo na conciliacao."""

    def test_caminho_completo_acordo_conciliacao(self) -> None:
        """Fluxo: peticao -> admissibilidade -> citacao -> conciliacao ->
        audiencia realizada -> acordo."""
        proc_id = "proc-jec-1"
        caminho = [
            ("PETICAO_INICIAL", "ANALISE_ADMISSIBILIDADE", "SECRETARIA"),
            ("ANALISE_ADMISSIBILIDADE", "CITACAO_EXPEDIDA", "SECRETARIA"),
            ("CITACAO_EXPEDIDA", "AUDIENCIA_CONCILIACAO_DESIGNADA", "SECRETARIA"),
            ("AUDIENCIA_CONCILIACAO_DESIGNADA", "AUDIENCIA_CONCILIACAO_REALIZADA", "CONCILIADOR"),
            ("AUDIENCIA_CONCILIACAO_REALIZADA", "ARQUIVADO_ACORDO_CONCILIACAO", "CONCILIADOR"),
        ]
        hash_anterior = ""
        for estado_atual, destino, ator_tipo in caminho:
            evento = engine.transicionar(
                estado_atual=estado_atual,
                estado_destino=destino,
                ator_id="ator-1",
                ator_tipo=ator_tipo,
                processo_id=proc_id,
                hash_anterior=hash_anterior,
            )
            assert evento.estado_novo == destino
            hash_anterior = evento.hash


# ======================================================================
# Fluxo feliz — caminho completo ate transito em julgado
# ======================================================================

class TestFluxoFelizSentenca:
    """Testa o caminho completo com sentenca e transito em julgado."""

    def test_caminho_completo_sentenca_sem_recurso(self) -> None:
        """Fluxo: peticao -> conciliacao -> contestacao -> instrucao ->
        sentenca -> transito em julgado."""
        proc_id = "proc-jec-2"
        caminho = [
            ("PETICAO_INICIAL", "ANALISE_ADMISSIBILIDADE", "SECRETARIA"),
            ("ANALISE_ADMISSIBILIDADE", "CITACAO_EXPEDIDA", "SECRETARIA"),
            ("CITACAO_EXPEDIDA", "AUDIENCIA_CONCILIACAO_DESIGNADA", "SECRETARIA"),
            ("AUDIENCIA_CONCILIACAO_DESIGNADA", "AUDIENCIA_CONCILIACAO_REALIZADA", "CONCILIADOR"),
            ("AUDIENCIA_CONCILIACAO_REALIZADA", "CONTESTACAO_RECEBIDA", "SECRETARIA"),
            ("CONTESTACAO_RECEBIDA", "AUDIENCIA_INSTRUCAO_DESIGNADA", "JUIZ"),
            ("AUDIENCIA_INSTRUCAO_DESIGNADA", "AUDIENCIA_INSTRUCAO_REALIZADA", "JUIZ"),
            ("AUDIENCIA_INSTRUCAO_REALIZADA", "CONCLUSO_SENTENCA", "JUIZ"),
            ("CONCLUSO_SENTENCA", "SENTENCA_PROFERIDA", "JUIZ"),
            ("SENTENCA_PROFERIDA", "TRANSITADO_EM_JULGADO", "SECRETARIA"),
        ]
        hash_anterior = ""
        for estado_atual, destino, ator_tipo in caminho:
            evento = engine.transicionar(
                estado_atual=estado_atual,
                estado_destino=destino,
                ator_id="ator-1",
                ator_tipo=ator_tipo,
                processo_id=proc_id,
                hash_anterior=hash_anterior,
            )
            assert evento.estado_novo == destino
            hash_anterior = evento.hash

    def test_caminho_com_recurso(self) -> None:
        """Fluxo com recurso inominado para Turma Recursal (art. 41)."""
        proc_id = "proc-jec-3"
        caminho = [
            ("SENTENCA_PROFERIDA", "RECURSO_INTERPOSTO", "PARTE"),
            ("RECURSO_INTERPOSTO", "RECURSO_JULGADO", "TURMA_RECURSAL"),
            ("RECURSO_JULGADO", "TRANSITADO_EM_JULGADO", "SECRETARIA"),
        ]
        for estado_atual, destino, ator_tipo in caminho:
            evento = engine.transicionar(
                estado_atual=estado_atual,
                estado_destino=destino,
                ator_id="ator-1",
                ator_tipo=ator_tipo,
                processo_id=proc_id,
            )
            assert evento.estado_novo == destino

    def test_julgamento_antecipado(self) -> None:
        """Materia exclusivamente de direito — vai direto a sentenca."""
        proc_id = "proc-jec-4"
        caminho = [
            ("CONTESTACAO_RECEBIDA", "CONCLUSO_SENTENCA", "JUIZ"),
            ("CONCLUSO_SENTENCA", "SENTENCA_PROFERIDA", "JUIZ"),
        ]
        for estado_atual, destino, ator_tipo in caminho:
            evento = engine.transicionar(
                estado_atual=estado_atual,
                estado_destino=destino,
                ator_id="ator-1",
                ator_tipo=ator_tipo,
                processo_id=proc_id,
            )
            assert evento.estado_novo == destino

    def test_acordo_em_instrucao(self) -> None:
        """Acordo obtido durante audiencia de instrucao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_INSTRUCAO_REALIZADA",
            estado_destino="ARQUIVADO_ACORDO_INSTRUCAO",
            ator_id="ator-1",
            ator_tipo="JUIZ",
            processo_id="proc-jec-5",
        )
        assert evento.estado_novo == "ARQUIVADO_ACORDO_INSTRUCAO"


# ======================================================================
# Caminhos alternativos — arquivamentos e terminais
# ======================================================================

class TestArquivamentos:
    """Testa todos os caminhos de arquivamento."""

    def test_extincao_inadmissibilidade(self) -> None:
        """art. 51 — causa inadmissivel (valor, competencia)."""
        evento = engine.transicionar(
            estado_atual="ANALISE_ADMISSIBILIDADE",
            estado_destino="ARQUIVADO_EXTINCAO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_EXTINCAO"

    def test_extincao_citacao_frustrada(self) -> None:
        """art. 51 — citacao frustrada."""
        evento = engine.transicionar(
            estado_atual="CITACAO_EXPEDIDA",
            estado_destino="ARQUIVADO_EXTINCAO",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_EXTINCAO"

    def test_revelia_audiencia_conciliacao(self) -> None:
        """art. 20 — reu ausente na audiencia de conciliacao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_CONCILIACAO_DESIGNADA",
            estado_destino="ARQUIVADO_REVELIA",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_REVELIA"

    def test_revelia_apos_conciliacao(self) -> None:
        """art. 20 — reu nao contesta apos conciliacao frustrada."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_CONCILIACAO_REALIZADA",
            estado_destino="ARQUIVADO_REVELIA",
            ator_id="ator-1",
            ator_tipo="JUIZ",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_REVELIA"

    def test_desistencia_antes_conciliacao(self) -> None:
        """art. 51 I — autor desiste antes da conciliacao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_CONCILIACAO_DESIGNADA",
            estado_destino="ARQUIVADO_DESISTENCIA",
            ator_id="ator-1",
            ator_tipo="PARTE",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_DESISTENCIA"

    def test_desistencia_antes_instrucao(self) -> None:
        """art. 51 I — autor desiste antes da instrucao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_INSTRUCAO_DESIGNADA",
            estado_destino="ARQUIVADO_DESISTENCIA",
            ator_id="ator-1",
            ator_tipo="PARTE",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_DESISTENCIA"


# ======================================================================
# Transicoes invalidas — prevencao de nulidades por design
# ======================================================================

class TestTransicoesInvalidas:
    """Verifica que transicoes fora do fluxo levantam excecao."""

    def test_pular_admissibilidade(self) -> None:
        """Nao pode ir de PETICAO_INICIAL direto a CITACAO_EXPEDIDA."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="PETICAO_INICIAL",
                estado_destino="CITACAO_EXPEDIDA",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_pular_conciliacao(self) -> None:
        """art. 21 — conciliacao e obrigatoria, nao pode pular."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="CITACAO_EXPEDIDA",
                estado_destino="CONTESTACAO_RECEBIDA",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_sentenca_sem_instrucao(self) -> None:
        """Nao pode proferir sentenca sem estar concluso."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="AUDIENCIA_INSTRUCAO_REALIZADA",
                estado_destino="SENTENCA_PROFERIDA",
                ator_id="ator-1",
                ator_tipo="JUIZ",
                processo_id="proc-1",
            )

    def test_voltar_estado(self) -> None:
        """Nao pode voltar a estados anteriores."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="CONTESTACAO_RECEBIDA",
                estado_destino="AUDIENCIA_CONCILIACAO_REALIZADA",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_recurso_sem_sentenca(self) -> None:
        """Nao pode interpor recurso sem sentenca proferida."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="CONCLUSO_SENTENCA",
                estado_destino="RECURSO_INTERPOSTO",
                ator_id="ator-1",
                ator_tipo="PARTE",
                processo_id="proc-1",
            )

    def test_acordo_direto_de_contestacao(self) -> None:
        """Nao pode obter acordo direto da contestacao."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="CONTESTACAO_RECEBIDA",
                estado_destino="ARQUIVADO_ACORDO_CONCILIACAO",
                ator_id="ator-1",
                ator_tipo="CONCILIADOR",
                processo_id="proc-1",
            )


# ======================================================================
# Estados terminais — frozen
# ======================================================================

class TestEstadosTerminais:
    """Verifica que estados terminais sao imutaveis por design."""

    @pytest.mark.parametrize("terminal", [
        "ARQUIVADO_ACORDO_CONCILIACAO",
        "ARQUIVADO_ACORDO_INSTRUCAO",
        "ARQUIVADO_REVELIA",
        "ARQUIVADO_DESISTENCIA",
        "ARQUIVADO_EXTINCAO",
        "TRANSITADO_EM_JULGADO",
    ])
    def test_terminal_sem_saida(self, terminal: str) -> None:
        with pytest.raises(EstadoTerminal):
            engine.transicionar(
                estado_atual=terminal,
                estado_destino="PETICAO_INICIAL",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    @pytest.mark.parametrize("terminal", list(ESTADOS_TERMINAIS))
    def test_is_terminal(self, terminal: str) -> None:
        assert engine.is_terminal(terminal) is True

    def test_fluxo_nao_e_terminal(self) -> None:
        estados_fluxo = [
            "PETICAO_INICIAL", "ANALISE_ADMISSIBILIDADE", "CITACAO_EXPEDIDA",
            "AUDIENCIA_CONCILIACAO_DESIGNADA", "AUDIENCIA_CONCILIACAO_REALIZADA",
            "CONTESTACAO_RECEBIDA", "AUDIENCIA_INSTRUCAO_DESIGNADA",
            "AUDIENCIA_INSTRUCAO_REALIZADA", "CONCLUSO_SENTENCA",
            "SENTENCA_PROFERIDA", "RECURSO_INTERPOSTO", "RECURSO_JULGADO",
        ]
        for estado in estados_fluxo:
            assert engine.is_terminal(estado) is False


# ======================================================================
# Permissoes — cada ator so pode agir em seu estado
# ======================================================================

class TestPermissoes:
    """Verifica que atores nao autorizados sao barrados."""

    def test_parte_nao_pode_triar(self) -> None:
        """PARTE nao pode fazer analise de admissibilidade."""
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="PETICAO_INICIAL",
                estado_destino="ANALISE_ADMISSIBILIDADE",
                ator_id="ator-1",
                ator_tipo="PARTE",
                processo_id="proc-1",
            )

    def test_parte_nao_pode_conduzir_conciliacao(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="AUDIENCIA_CONCILIACAO_DESIGNADA",
                estado_destino="AUDIENCIA_CONCILIACAO_REALIZADA",
                ator_id="ator-1",
                ator_tipo="PARTE",
                processo_id="proc-1",
            )

    def test_secretaria_nao_pode_proferir_sentenca(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="CONCLUSO_SENTENCA",
                estado_destino="SENTENCA_PROFERIDA",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_conciliador_pode_conduzir_conciliacao(self) -> None:
        """art. 22 — conciliador conduz audiencia de conciliacao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_CONCILIACAO_DESIGNADA",
            estado_destino="AUDIENCIA_CONCILIACAO_REALIZADA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "AUDIENCIA_CONCILIACAO_REALIZADA"

    def test_juiz_pode_proferir_sentenca(self) -> None:
        """art. 38 — juiz profere sentenca."""
        evento = engine.transicionar(
            estado_atual="CONCLUSO_SENTENCA",
            estado_destino="SENTENCA_PROFERIDA",
            ator_id="ator-1",
            ator_tipo="JUIZ",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "SENTENCA_PROFERIDA"

    def test_parte_pode_interpor_recurso(self) -> None:
        """art. 41 — parte pode interpor recurso."""
        evento = engine.transicionar(
            estado_atual="SENTENCA_PROFERIDA",
            estado_destino="RECURSO_INTERPOSTO",
            ator_id="ator-1",
            ator_tipo="PARTE",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "RECURSO_INTERPOSTO"

    def test_advogado_pode_interpor_recurso(self) -> None:
        """art. 41 — advogado pode interpor recurso pelo cliente."""
        evento = engine.transicionar(
            estado_atual="SENTENCA_PROFERIDA",
            estado_destino="RECURSO_INTERPOSTO",
            ator_id="ator-1",
            ator_tipo="ADVOGADO",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "RECURSO_INTERPOSTO"

    def test_turma_recursal_julga_recurso(self) -> None:
        """art. 46 — Turma Recursal julga recurso."""
        evento = engine.transicionar(
            estado_atual="RECURSO_INTERPOSTO",
            estado_destino="RECURSO_JULGADO",
            ator_id="ator-1",
            ator_tipo="TURMA_RECURSAL",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "RECURSO_JULGADO"

    def test_conciliador_nao_pode_julgar_recurso(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="RECURSO_INTERPOSTO",
                estado_destino="RECURSO_JULGADO",
                ator_id="ator-1",
                ator_tipo="CONCILIADOR",
                processo_id="proc-1",
            )

    def test_juiz_pode_conduzir_instrucao(self) -> None:
        """art. 27 — juiz preside audiencia de instrucao."""
        evento = engine.transicionar(
            estado_atual="AUDIENCIA_INSTRUCAO_DESIGNADA",
            estado_destino="AUDIENCIA_INSTRUCAO_REALIZADA",
            ator_id="ator-1",
            ator_tipo="JUIZ",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "AUDIENCIA_INSTRUCAO_REALIZADA"


# ======================================================================
# Prazos e competencia
# ======================================================================

class TestPrazosECompetencia:
    """Verifica as constantes de prazos e materias excluidas."""

    def test_prazo_citacao_15_dias(self) -> None:
        """art. 18 §1o"""
        assert PRAZO_CITACAO.days == 15

    def test_prazo_audiencia_conciliacao_15_dias(self) -> None:
        """art. 20"""
        assert PRAZO_AUDIENCIA_CONCILIACAO.days == 15

    def test_prazo_recurso_10_dias(self) -> None:
        """art. 42"""
        assert PRAZO_RECURSO.days == 10

    def test_prazo_cumprimento_sentenca_15_dias(self) -> None:
        """art. 52 IV"""
        assert PRAZO_CUMPRIMENTO_SENTENCA.days == 15

    def test_prazo_audiencia_instrucao_15_dias(self) -> None:
        """art. 27"""
        assert PRAZO_AUDIENCIA_INSTRUCAO.days == 15

    def test_salario_minimo_2025(self) -> None:
        from decimal import Decimal
        assert SALARIO_MINIMO == Decimal("1518.00")

    def test_valor_maximo_40_sm(self) -> None:
        """art. 3o I — ate 40 salarios minimos."""
        from decimal import Decimal
        assert VALOR_MAXIMO_CAUSA == Decimal("1518.00") * 40

    def test_limite_sem_advogado_20_sm(self) -> None:
        """art. 9o — advogado facultativo ate 20 SM."""
        from decimal import Decimal
        assert LIMITE_SEM_ADVOGADO == Decimal("1518.00") * 20

    def test_seis_materias_excluidas(self) -> None:
        """art. 3o §2o — materias excluidas."""
        assert len(MATERIAS_EXCLUIDAS) == 6

    def test_cada_materia_tem_artigo(self) -> None:
        for materia in MATERIAS_EXCLUIDAS:
            assert "artigo" in materia, f"Materia sem artigo: {materia}"
            assert "codigo" in materia
            assert "descricao" in materia


# ======================================================================
# Transicoes validas — cobertura de todas as saidas
# ======================================================================

class TestTransicoesValidas:
    """Verifica que transicoes_validas() retorna as saidas corretas."""

    def test_peticao_inicial(self) -> None:
        assert engine.transicoes_validas("PETICAO_INICIAL") == [
            EstadoJEC.ANALISE_ADMISSIBILIDADE,
        ]

    def test_analise_admissibilidade(self) -> None:
        validas = engine.transicoes_validas("ANALISE_ADMISSIBILIDADE")
        assert EstadoJEC.CITACAO_EXPEDIDA in validas
        assert EstadoJEC.ARQUIVADO_EXTINCAO in validas

    def test_audiencia_conciliacao_realizada(self) -> None:
        validas = engine.transicoes_validas("AUDIENCIA_CONCILIACAO_REALIZADA")
        assert EstadoJEC.ARQUIVADO_ACORDO_CONCILIACAO in validas
        assert EstadoJEC.CONTESTACAO_RECEBIDA in validas
        assert EstadoJEC.ARQUIVADO_REVELIA in validas

    def test_contestacao_recebida(self) -> None:
        validas = engine.transicoes_validas("CONTESTACAO_RECEBIDA")
        assert EstadoJEC.AUDIENCIA_INSTRUCAO_DESIGNADA in validas
        assert EstadoJEC.CONCLUSO_SENTENCA in validas

    def test_sentenca_proferida(self) -> None:
        validas = engine.transicoes_validas("SENTENCA_PROFERIDA")
        assert EstadoJEC.RECURSO_INTERPOSTO in validas
        assert EstadoJEC.TRANSITADO_EM_JULGADO in validas

    def test_terminais_sem_saida(self) -> None:
        """Todos os terminais devem retornar lista vazia."""
        for terminal in ESTADOS_TERMINAIS:
            assert engine.transicoes_validas(terminal) == []
