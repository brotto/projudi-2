"""
Testes da FSM do CEJUSC pré-processual — cobertura 100% de estados e transições.

Testa:
- Todas as transições válidas da Res. 403/2023
- Rejeição de transições inválidas
- Estados terminais (frozen)
- Permissões por ator
- Prazos legais
- Matérias excluídas da competência
- Consistência da definição FSM
"""

from __future__ import annotations

import pytest

from juizo.exceptions import AtorNaoAutorizado, EstadoTerminal, TransicaoInvalida

from fsm.engine import cejusc_pre_fsm, engine
from fsm.estados import (
    ESTADOS_TERMINAIS,
    EstadoCejusc,
    MATERIAS_EXCLUIDAS,
    PERMISSOES,
    PRAZO_MAX_CONTINUADA,
    PRAZO_MAX_SEM_SESSAO,
    PRAZO_REGULARIZACAO,
    TRANSICOES,
)


# ══════════════════════════════════════════════════════════════════════════
# Validação da definição FSM
# ══════════════════════════════════════════════════════════════════════════

class TestDefinicaoFSM:
    """Verifica a consistência da definição da FSM."""

    def test_definicao_valida(self) -> None:
        erros = cejusc_pre_fsm.validar_definicao()
        assert erros == [], f"Definição FSM inválida: {erros}"

    def test_todos_estados_enum_presentes_em_transicoes(self) -> None:
        """Cada valor do Enum deve ter uma entrada no dict de transições."""
        for estado in EstadoCejusc:
            assert estado in TRANSICOES, f"Estado {estado} ausente das transições"

    def test_todos_estados_terminais_sem_saida(self) -> None:
        for terminal in ESTADOS_TERMINAIS:
            assert TRANSICOES[terminal] == [], (
                f"Terminal {terminal} tem transições de saída"
            )

    def test_seis_estados_terminais(self) -> None:
        assert len(ESTADOS_TERMINAIS) == 6

    def test_total_estados(self) -> None:
        """13 estados de fluxo + 6 terminais = 19."""
        assert len(EstadoCejusc) == 19

    def test_todos_estados_tem_permissao(self) -> None:
        """Cada estado (exceto SOLICITACAO_RECEBIDA) deve ter permissões."""
        for estado in EstadoCejusc:
            if estado == EstadoCejusc.SOLICITACAO_RECEBIDA:
                continue  # estado inicial — pode ser criado por qualquer um
            assert estado in PERMISSOES, (
                f"Estado {estado} não tem permissões definidas"
            )


# ══════════════════════════════════════════════════════════════════════════
# Fluxo feliz — caminho completo da reclamação
# ══════════════════════════════════════════════════════════════════════════

class TestFluxoFeliz:
    """Testa o caminho completo de uma reclamação com acordo."""

    def test_caminho_completo_com_acordo(self) -> None:
        """Fluxo: recebida → triagem → custas → cadastrado → agendada →
        notificações → sessão → acordo → concluso → homologado → arquivado."""
        proc_id = "proc-teste-1"
        caminho = [
            ("SOLICITACAO_RECEBIDA", "TRIAGEM", "SECRETARIA"),
            ("TRIAGEM", "VERIFICACAO_CUSTAS", "SECRETARIA"),
            ("VERIFICACAO_CUSTAS", "CADASTRADO", "SECRETARIA"),
            ("CADASTRADO", "SESSAO_AGENDADA", "SECRETARIA"),
            ("SESSAO_AGENDADA", "NOTIFICACOES_ENVIADAS", "SECRETARIA"),
            ("NOTIFICACOES_ENVIADAS", "SESSAO_CONDUZIDA", "CONCILIADOR"),
            ("SESSAO_CONDUZIDA", "ACORDO_REDIGIDO", "CONCILIADOR"),
            ("ACORDO_REDIGIDO", "CONCLUSO_JUIZ", "SECRETARIA"),
            ("CONCLUSO_JUIZ", "HOMOLOGADO", "JUIZ_COORDENADOR"),
            ("HOMOLOGADO", "ARQUIVADO_ACORDO", "SECRETARIA"),
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

    def test_caminho_com_gratuidade(self) -> None:
        """Fluxo com pedido de gratuidade deferido."""
        proc_id = "proc-teste-2"
        caminho = [
            ("SOLICITACAO_RECEBIDA", "TRIAGEM", "SECRETARIA"),
            ("TRIAGEM", "VERIFICACAO_CUSTAS", "SECRETARIA"),
            ("VERIFICACAO_CUSTAS", "ANALISE_GRATUIDADE", "SECRETARIA"),
            ("ANALISE_GRATUIDADE", "CADASTRADO", "JUIZ_COORDENADOR"),
            ("CADASTRADO", "SESSAO_AGENDADA", "SECRETARIA"),
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

    def test_caminho_com_mp(self) -> None:
        """Fluxo com menores/incapazes — MP obrigatório (art. 15 §ú)."""
        proc_id = "proc-teste-3"
        caminho = [
            ("ACORDO_REDIGIDO", "AGUARDANDO_MP", "SECRETARIA"),
            ("AGUARDANDO_MP", "CONCLUSO_JUIZ", "SECRETARIA"),
            ("CONCLUSO_JUIZ", "HOMOLOGADO", "JUIZ_COORDENADOR"),
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

    def test_sessao_continuada(self) -> None:
        """art. 12 §4º — sessão pode ser continuada (max 60 dias total)."""
        proc_id = "proc-teste-4"
        # Primeira sessão → continuação
        evento = engine.transicionar(
            estado_atual="SESSAO_CONDUZIDA",
            estado_destino="SESSAO_CONTINUADA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id=proc_id,
        )
        assert evento.estado_novo == "SESSAO_CONTINUADA"

        # Continuação → outra continuação (loop permitido)
        evento = engine.transicionar(
            estado_atual="SESSAO_CONTINUADA",
            estado_destino="SESSAO_CONTINUADA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id=proc_id,
        )
        assert evento.estado_novo == "SESSAO_CONTINUADA"

        # Continuação → acordo
        evento = engine.transicionar(
            estado_atual="SESSAO_CONTINUADA",
            estado_destino="ACORDO_REDIGIDO",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id=proc_id,
        )
        assert evento.estado_novo == "ACORDO_REDIGIDO"


# ══════════════════════════════════════════════════════════════════════════
# Arquivamentos — caminhos alternativos
# ══════════════════════════════════════════════════════════════════════════

class TestArquivamentos:
    """Testa todos os caminhos de arquivamento."""

    def test_arquivado_incompetente(self) -> None:
        """art. 6º §1º — matéria excluída da competência."""
        evento = engine.transicionar(
            estado_atual="TRIAGEM",
            estado_destino="ARQUIVADO_INCOMPETENTE",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_INCOMPETENTE"

    def test_arquivado_irregular(self) -> None:
        """art. 9º §2º — não regularizou em 5 dias."""
        evento = engine.transicionar(
            estado_atual="TRIAGEM",
            estado_destino="ARQUIVADO_IRREGULAR",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_IRREGULAR"

    def test_arquivado_falta_custas_verificacao(self) -> None:
        """art. 8º §4º — não recolheu taxa."""
        evento = engine.transicionar(
            estado_atual="VERIFICACAO_CUSTAS",
            estado_destino="ARQUIVADO_FALTA_CUSTAS",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_FALTA_CUSTAS"

    def test_arquivado_falta_custas_analise(self) -> None:
        """Gratuidade indeferida + não pagou."""
        evento = engine.transicionar(
            estado_atual="ANALISE_GRATUIDADE",
            estado_destino="ARQUIVADO_FALTA_CUSTAS",
            ator_id="ator-1",
            ator_tipo="JUIZ_COORDENADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_FALTA_CUSTAS"

    def test_arquivado_ausencia_notificacao(self) -> None:
        """art. 12 §3º — ausência após notificação."""
        evento = engine.transicionar(
            estado_atual="NOTIFICACOES_ENVIADAS",
            estado_destino="ARQUIVADO_AUSENCIA",
            ator_id="ator-1",
            ator_tipo="SECRETARIA",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_AUSENCIA"

    def test_arquivado_ausencia_sessao(self) -> None:
        """art. 12 §3º — ausência durante sessão."""
        evento = engine.transicionar(
            estado_atual="SESSAO_CONDUZIDA",
            estado_destino="ARQUIVADO_AUSENCIA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_AUSENCIA"

    def test_arquivado_ausencia_continuacao(self) -> None:
        """Ausência em sessão continuada."""
        evento = engine.transicionar(
            estado_atual="SESSAO_CONTINUADA",
            estado_destino="ARQUIVADO_AUSENCIA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_AUSENCIA"

    def test_arquivado_sem_acordo_sessao(self) -> None:
        """art. 12 §3º — sessão infrutífera."""
        evento = engine.transicionar(
            estado_atual="SESSAO_CONDUZIDA",
            estado_destino="ARQUIVADO_SEM_ACORDO",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_SEM_ACORDO"

    def test_arquivado_sem_acordo_continuacao(self) -> None:
        """Sessão continuada infrutífera."""
        evento = engine.transicionar(
            estado_atual="SESSAO_CONTINUADA",
            estado_destino="ARQUIVADO_SEM_ACORDO",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "ARQUIVADO_SEM_ACORDO"


# ══════════════════════════════════════════════════════════════════════════
# Transições inválidas — prevenção de nulidades por design
# ══════════════════════════════════════════════════════════════════════════

class TestTransicoesInvalidas:
    """Verifica que transições fora do fluxo levantam exceção."""

    def test_pular_triagem(self) -> None:
        """Não pode ir de SOLICITACAO_RECEBIDA direto a CADASTRADO."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="SOLICITACAO_RECEBIDA",
                estado_destino="CADASTRADO",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_pular_custas(self) -> None:
        """Não pode ir de TRIAGEM direto a CADASTRADO (precisa verificar custas)."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="TRIAGEM",
                estado_destino="CADASTRADO",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_voltar_estado(self) -> None:
        """Não pode voltar a estados anteriores."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="SESSAO_AGENDADA",
                estado_destino="CADASTRADO",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_acordo_sem_sessao(self) -> None:
        """Não pode ter acordo sem sessão."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="NOTIFICACOES_ENVIADAS",
                estado_destino="ACORDO_REDIGIDO",
                ator_id="ator-1",
                ator_tipo="CONCILIADOR",
                processo_id="proc-1",
            )

    def test_homologar_sem_concluso(self) -> None:
        """Não pode homologar sem estar concluso ao juiz."""
        with pytest.raises(TransicaoInvalida):
            engine.transicionar(
                estado_atual="ACORDO_REDIGIDO",
                estado_destino="HOMOLOGADO",
                ator_id="ator-1",
                ator_tipo="JUIZ_COORDENADOR",
                processo_id="proc-1",
            )


# ══════════════════════════════════════════════════════════════════════════
# Estados terminais — frozen
# ══════════════════════════════════════════════════════════════════════════

class TestEstadosTerminais:
    """Verifica que estados terminais são imutáveis por design."""

    @pytest.mark.parametrize("terminal", [
        "ARQUIVADO_ACORDO",
        "ARQUIVADO_SEM_ACORDO",
        "ARQUIVADO_AUSENCIA",
        "ARQUIVADO_FALTA_CUSTAS",
        "ARQUIVADO_INCOMPETENTE",
        "ARQUIVADO_IRREGULAR",
    ])
    def test_terminal_sem_saida(self, terminal: str) -> None:
        with pytest.raises(EstadoTerminal):
            engine.transicionar(
                estado_atual=terminal,
                estado_destino="SOLICITACAO_RECEBIDA",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    @pytest.mark.parametrize("terminal", list(ESTADOS_TERMINAIS))
    def test_is_terminal(self, terminal: str) -> None:
        assert engine.is_terminal(terminal) is True

    def test_fluxo_nao_e_terminal(self) -> None:
        estados_fluxo = [
            "SOLICITACAO_RECEBIDA", "TRIAGEM", "VERIFICACAO_CUSTAS",
            "ANALISE_GRATUIDADE", "CADASTRADO", "SESSAO_AGENDADA",
            "NOTIFICACOES_ENVIADAS", "SESSAO_CONDUZIDA", "SESSAO_CONTINUADA",
            "ACORDO_REDIGIDO", "AGUARDANDO_MP", "CONCLUSO_JUIZ", "HOMOLOGADO",
        ]
        for estado in estados_fluxo:
            assert engine.is_terminal(estado) is False


# ══════════════════════════════════════════════════════════════════════════
# Permissões — cada ator só pode agir em seu estado
# ══════════════════════════════════════════════════════════════════════════

class TestPermissoes:
    """Verifica que atores não autorizados são barrados."""

    def test_parte_nao_pode_triar(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="SOLICITACAO_RECEBIDA",
                estado_destino="TRIAGEM",
                ator_id="ator-1",
                ator_tipo="PARTE",
                processo_id="proc-1",
            )

    def test_parte_nao_pode_conduzir_sessao(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="NOTIFICACOES_ENVIADAS",
                estado_destino="SESSAO_CONDUZIDA",
                ator_id="ator-1",
                ator_tipo="PARTE",
                processo_id="proc-1",
            )

    def test_secretaria_nao_pode_homologar(self) -> None:
        with pytest.raises(AtorNaoAutorizado):
            engine.transicionar(
                estado_atual="CONCLUSO_JUIZ",
                estado_destino="HOMOLOGADO",
                ator_id="ator-1",
                ator_tipo="SECRETARIA",
                processo_id="proc-1",
            )

    def test_conciliador_pode_conduzir(self) -> None:
        evento = engine.transicionar(
            estado_atual="NOTIFICACOES_ENVIADAS",
            estado_destino="SESSAO_CONDUZIDA",
            ator_id="ator-1",
            ator_tipo="CONCILIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "SESSAO_CONDUZIDA"

    def test_mediador_pode_conduzir(self) -> None:
        evento = engine.transicionar(
            estado_atual="NOTIFICACOES_ENVIADAS",
            estado_destino="SESSAO_CONDUZIDA",
            ator_id="ator-1",
            ator_tipo="MEDIADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "SESSAO_CONDUZIDA"

    def test_juiz_pode_homologar(self) -> None:
        evento = engine.transicionar(
            estado_atual="CONCLUSO_JUIZ",
            estado_destino="HOMOLOGADO",
            ator_id="ator-1",
            ator_tipo="JUIZ_COORDENADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "HOMOLOGADO"

    def test_juiz_coordenador_analisa_gratuidade(self) -> None:
        """Análise de gratuidade é ato do juiz coordenador."""
        evento = engine.transicionar(
            estado_atual="ANALISE_GRATUIDADE",
            estado_destino="CADASTRADO",
            ator_id="ator-1",
            ator_tipo="JUIZ_COORDENADOR",
            processo_id="proc-1",
        )
        assert evento.estado_novo == "CADASTRADO"


# ══════════════════════════════════════════════════════════════════════════
# Prazos e matérias excluídas
# ══════════════════════════════════════════════════════════════════════════

class TestPrazosECompetencia:
    """Verifica as constantes de prazos e matérias excluídas."""

    def test_prazo_regularizacao_5_dias(self) -> None:
        """art. 9º §2º"""
        assert PRAZO_REGULARIZACAO.days == 5

    def test_prazo_max_sem_sessao_30_dias(self) -> None:
        """art. 14"""
        assert PRAZO_MAX_SEM_SESSAO.days == 30

    def test_prazo_max_continuada_60_dias(self) -> None:
        """art. 14"""
        assert PRAZO_MAX_CONTINUADA.days == 60

    def test_oito_materias_excluidas(self) -> None:
        """art. 6º §1º — 8 matérias excluídas."""
        assert len(MATERIAS_EXCLUIDAS) == 8

    def test_cada_materia_tem_artigo(self) -> None:
        for materia in MATERIAS_EXCLUIDAS:
            assert "artigo" in materia, f"Matéria sem artigo: {materia}"
            assert "codigo" in materia
            assert "descricao" in materia


# ══════════════════════════════════════════════════════════════════════════
# Transições válidas — cobertura de todas as saídas
# ══════════════════════════════════════════════════════════════════════════

class TestTransicoesValidas:
    """Verifica que transicoes_validas() retorna as saídas corretas."""

    def test_solicitacao_recebida(self) -> None:
        assert engine.transicoes_validas("SOLICITACAO_RECEBIDA") == [
            EstadoCejusc.TRIAGEM,
        ]

    def test_triagem(self) -> None:
        validas = engine.transicoes_validas("TRIAGEM")
        assert EstadoCejusc.VERIFICACAO_CUSTAS in validas
        assert EstadoCejusc.ARQUIVADO_INCOMPETENTE in validas
        assert EstadoCejusc.ARQUIVADO_IRREGULAR in validas

    def test_verificacao_custas(self) -> None:
        validas = engine.transicoes_validas("VERIFICACAO_CUSTAS")
        assert EstadoCejusc.CADASTRADO in validas
        assert EstadoCejusc.ANALISE_GRATUIDADE in validas
        assert EstadoCejusc.ARQUIVADO_FALTA_CUSTAS in validas

    def test_sessao_conduzida(self) -> None:
        validas = engine.transicoes_validas("SESSAO_CONDUZIDA")
        assert EstadoCejusc.SESSAO_CONTINUADA in validas
        assert EstadoCejusc.ACORDO_REDIGIDO in validas
        assert EstadoCejusc.ARQUIVADO_SEM_ACORDO in validas
        assert EstadoCejusc.ARQUIVADO_AUSENCIA in validas

    def test_sessao_continuada_permite_loop(self) -> None:
        """SESSAO_CONTINUADA pode ir a si mesma."""
        validas = engine.transicoes_validas("SESSAO_CONTINUADA")
        assert EstadoCejusc.SESSAO_CONTINUADA in validas

    def test_acordo_redigido(self) -> None:
        validas = engine.transicoes_validas("ACORDO_REDIGIDO")
        assert EstadoCejusc.AGUARDANDO_MP in validas
        assert EstadoCejusc.CONCLUSO_JUIZ in validas
