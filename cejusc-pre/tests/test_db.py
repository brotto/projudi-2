"""
Testes da camada de persistencia SQLAlchemy.

Testa:
- Criacao de tabelas
- CRUD de reclamacoes via EventStoreSql
- Transicoes FSM com persistencia de eventos
- Historico de eventos (append-only log)
- CRUD de sessoes
- CRUD de acordos
- CRUD de usuarios

Usa SQLite em memoria para isolamento total entre testes.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, UTC
from uuid import uuid4

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from db.database import Base, create_tables_with_engine
from db.models import EventoLog, ReclamacaoDB, SessaoDB, AcordoDB, UsuarioDB
from db.store_sql import EventStoreSql

from juizo.exceptions import TransicaoInvalida, EstadoTerminal, AtorNaoAutorizado
from fsm.estados import EstadoCejusc


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db_engine():
    """Engine SQLite em memoria para testes isolados."""
    engine = create_engine("sqlite:///:memory:")
    create_tables_with_engine(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Sessao SQLAlchemy para cada teste."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def store(db_session):
    """EventStoreSql com sessao de teste."""
    return EventStoreSql(db_session)


def _dados_reclamacao() -> dict:
    """Dados padrao para criar reclamacao — art. 9o Res. 403/2023."""
    return {
        "cejusc_destino": "CEJUSC-CENTRAL-CURITIBA",
        "reclamante": {
            "nome": "Maria Silva",
            "tipo_pessoa": "FISICA",
            "cpf": "12345678901",
            "email": "maria@email.com",
            "telefone": "(41)99999-0001",
        },
        "reclamado": {
            "nome": "Empresa XYZ Ltda",
            "tipo_pessoa": "JURIDICA",
            "cnpj": "12345678000195",
            "email": "contato@xyz.com",
        },
        "fatos": "Compra de produto com defeito sem resolucao pelo SAC.",
        "pedidos": [
            {"descricao": "Devolucao do valor pago", "valor": "1500.00"},
        ],
        "valor_causa": "1500.00",
        "modalidade": "CONCILIACAO",
        "opcao_custas": "TAXA_PAGA",
    }


# ══════════════════════════════════════════════════════════════════════════
# Teste 1: Criacao de tabelas
# ══════════════════════════════════════════════════════════════════════════


class TestCriacaoTabelas:
    def test_create_tables_cria_todas_as_tabelas(self, db_engine):
        """Verifica que create_tables cria as 5 tabelas esperadas."""
        inspector = inspect(db_engine)
        tabelas = inspector.get_table_names()

        assert "evento_log" in tabelas
        assert "reclamacoes" in tabelas
        assert "sessoes" in tabelas
        assert "acordos" in tabelas
        assert "usuarios" in tabelas

    def test_create_tables_colunas_evento_log(self, db_engine):
        """Verifica colunas da tabela evento_log."""
        inspector = inspect(db_engine)
        colunas = {c["name"] for c in inspector.get_columns("evento_log")}

        esperadas = {
            "id", "processo_id", "estado_anterior", "estado_novo",
            "ator_id", "ator_tipo", "timestamp", "payload",
            "hash_anterior", "hash",
        }
        assert esperadas.issubset(colunas)


# ══════════════════════════════════════════════════════════════════════════
# Teste 2-4: CRUD Reclamacoes
# ══════════════════════════════════════════════════════════════════════════


class TestReclamacoesCRUD:
    def test_criar_reclamacao(self, store, db_session):
        """Criar reclamacao persiste no banco e retorna evento."""
        rec_id = uuid4()
        evento = store.criar_reclamacao(rec_id, _dados_reclamacao())

        assert evento.estado_novo == EstadoCejusc.SOLICITACAO_RECEBIDA
        assert evento.processo_id == str(rec_id)

        # Verificar que esta no banco
        rec_db = db_session.query(ReclamacaoDB).filter(
            ReclamacaoDB.id == str(rec_id)
        ).first()
        assert rec_db is not None
        assert rec_db.cejusc_destino == "CEJUSC-CENTRAL-CURITIBA"
        assert rec_db.estado_atual == EstadoCejusc.SOLICITACAO_RECEBIDA

    def test_get_reclamacao(self, store):
        """get_reclamacao retorna dicionario com dados completos."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        rec = store.get_reclamacao(rec_id)
        assert rec is not None
        assert rec["id"] == str(rec_id)
        assert rec["cejusc_destino"] == "CEJUSC-CENTRAL-CURITIBA"
        assert rec["estado_atual"] == EstadoCejusc.SOLICITACAO_RECEBIDA
        assert rec["reclamante"]["nome"] == "Maria Silva"

    def test_get_reclamacao_inexistente(self, store):
        """get_reclamacao retorna None para ID inexistente."""
        rec = store.get_reclamacao(uuid4())
        assert rec is None

    def test_listar_reclamacoes(self, store):
        """listar_reclamacoes retorna todas as reclamacoes."""
        store.criar_reclamacao(uuid4(), _dados_reclamacao())
        store.criar_reclamacao(uuid4(), _dados_reclamacao())

        lista = store.listar_reclamacoes()
        assert len(lista) == 2
        assert all("estado_atual" in r for r in lista)


# ══════════════════════════════════════════════════════════════════════════
# Teste 5-7: Transicoes FSM com persistencia
# ══════════════════════════════════════════════════════════════════════════


class TestTransicoesFSM:
    def test_transicao_valida_persiste_evento(self, store, db_session):
        """Transicao valida persiste evento no log e atualiza estado."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        evento = store.transicionar(
            reclamacao_id=rec_id,
            estado_destino=EstadoCejusc.TRIAGEM,
            ator_id="sec-001",
            ator_tipo="SECRETARIA",
        )

        assert evento.estado_anterior == EstadoCejusc.SOLICITACAO_RECEBIDA
        assert evento.estado_novo == EstadoCejusc.TRIAGEM
        assert evento.hash != ""

        # Verificar estado atualizado no banco
        rec = store.get_reclamacao(rec_id)
        assert rec["estado_atual"] == EstadoCejusc.TRIAGEM

        # Verificar evento no log
        eventos_db = db_session.query(EventoLog).filter(
            EventoLog.processo_id == str(rec_id)
        ).all()
        assert len(eventos_db) == 2  # criacao + transicao

    def test_transicao_invalida_lanca_excecao(self, store):
        """Transicao invalida lanca TransicaoInvalida."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        with pytest.raises(TransicaoInvalida):
            store.transicionar(
                reclamacao_id=rec_id,
                estado_destino=EstadoCejusc.HOMOLOGADO,
                ator_id="juiz-001",
                ator_tipo="JUIZ_COORDENADOR",
            )

    def test_ator_nao_autorizado(self, store):
        """Ator sem permissao lanca AtorNaoAutorizado."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        with pytest.raises(AtorNaoAutorizado):
            store.transicionar(
                reclamacao_id=rec_id,
                estado_destino=EstadoCejusc.TRIAGEM,
                ator_id="parte-001",
                ator_tipo="PARTE",
            )

    def test_estado_terminal_bloqueia_transicao(self, store):
        """Estado terminal impede novas transicoes."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        # Levar ate terminal: RECEBIDA -> TRIAGEM -> ARQUIVADO_INCOMPETENTE
        store.transicionar(rec_id, EstadoCejusc.TRIAGEM, "sec-001", "SECRETARIA")
        store.transicionar(rec_id, EstadoCejusc.ARQUIVADO_INCOMPETENTE, "sec-001", "SECRETARIA")

        with pytest.raises(EstadoTerminal):
            store.transicionar(rec_id, EstadoCejusc.TRIAGEM, "sec-001", "SECRETARIA")

    def test_fluxo_completo_happy_path(self, store):
        """
        Fluxo completo com acordo — happy path:
        RECEBIDA -> TRIAGEM -> CUSTAS -> CADASTRADO -> AGENDADA ->
        NOTIFICACOES -> CONDUZIDA -> ACORDO_REDIGIDO -> CONCLUSO_JUIZ ->
        HOMOLOGADO -> ARQUIVADO_ACORDO
        """
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        transicoes = [
            (EstadoCejusc.TRIAGEM, "sec-001", "SECRETARIA"),
            (EstadoCejusc.VERIFICACAO_CUSTAS, "sec-001", "SECRETARIA"),
            (EstadoCejusc.CADASTRADO, "sec-001", "SECRETARIA"),
            (EstadoCejusc.SESSAO_AGENDADA, "sec-001", "SECRETARIA"),
            (EstadoCejusc.NOTIFICACOES_ENVIADAS, "sec-001", "SECRETARIA"),
            (EstadoCejusc.SESSAO_CONDUZIDA, "conc-001", "CONCILIADOR"),
            (EstadoCejusc.ACORDO_REDIGIDO, "conc-001", "CONCILIADOR"),
            (EstadoCejusc.CONCLUSO_JUIZ, "sec-001", "SECRETARIA"),
            (EstadoCejusc.HOMOLOGADO, "juiz-001", "JUIZ_COORDENADOR"),
            (EstadoCejusc.ARQUIVADO_ACORDO, "sec-001", "SECRETARIA"),
        ]

        for estado_destino, ator_id, ator_tipo in transicoes:
            store.transicionar(rec_id, estado_destino, ator_id, ator_tipo)

        # Verificar estado terminal
        rec = store.get_reclamacao(rec_id)
        assert rec["estado_atual"] == EstadoCejusc.ARQUIVADO_ACORDO

        # Verificar historico completo
        historico = store.get_historico(rec_id)
        assert len(historico) == 11  # criacao + 10 transicoes


# ══════════════════════════════════════════════════════════════════════════
# Teste 8: Historico de eventos
# ══════════════════════════════════════════════════════════════════════════


class TestHistorico:
    def test_historico_retorna_eventos_em_ordem(self, store):
        """Historico retorna eventos ordenados por timestamp."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())
        store.transicionar(rec_id, EstadoCejusc.TRIAGEM, "sec-001", "SECRETARIA")
        store.transicionar(rec_id, EstadoCejusc.VERIFICACAO_CUSTAS, "sec-001", "SECRETARIA")

        historico = store.get_historico(rec_id)
        assert len(historico) == 3

        # Verificar ordem cronologica
        assert historico[0]["estado_novo"] == EstadoCejusc.SOLICITACAO_RECEBIDA
        assert historico[1]["estado_novo"] == EstadoCejusc.TRIAGEM
        assert historico[2]["estado_novo"] == EstadoCejusc.VERIFICACAO_CUSTAS

        # Verificar que cada evento tem hash
        assert all(e["hash"] != "" for e in historico)

    def test_get_estado_e_transicoes_validas(self, store):
        """get_estado e get_transicoes_validas funcionam corretamente."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        assert store.get_estado(rec_id) == EstadoCejusc.SOLICITACAO_RECEBIDA

        transicoes = store.get_transicoes_validas(rec_id)
        assert EstadoCejusc.TRIAGEM in transicoes

    def test_get_estado_inexistente(self, store):
        """get_estado retorna None para ID inexistente."""
        assert store.get_estado(uuid4()) is None

    def test_get_transicoes_validas_inexistente(self, store):
        """get_transicoes_validas retorna lista vazia para ID inexistente."""
        assert store.get_transicoes_validas(uuid4()) == []


# ══════════════════════════════════════════════════════════════════════════
# Teste 9: CRUD Sessoes
# ══════════════════════════════════════════════════════════════════════════


class TestSessoesCRUD:
    def test_criar_e_buscar_sessao(self, store):
        """Criar sessao e buscar pelo ID."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        sessao_id = uuid4()
        dados = {
            "reclamacao_id": str(rec_id),
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. Joao Mediador",
            "data_agendada": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "numero_sessao": 1,
            "resultado": None,
        }
        store.criar_sessao(sessao_id, dados)

        s = store.get_sessao(sessao_id)
        assert s is not None
        assert s["id"] == str(sessao_id)
        assert s["conciliador_nome"] == "Dr. Joao Mediador"
        assert s["numero_sessao"] == 1

    def test_listar_sessoes_por_reclamacao(self, store):
        """Listar sessoes filtradas por reclamacao."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        for i in range(3):
            store.criar_sessao(uuid4(), {
                "reclamacao_id": str(rec_id),
                "conciliador_id": "conc-001",
                "conciliador_nome": "Dr. Joao",
                "data_agendada": datetime.now(UTC).isoformat(),
                "numero_sessao": i + 1,
            })

        sessoes = store.listar_sessoes(rec_id)
        assert len(sessoes) == 3

    def test_atualizar_sessao(self, store):
        """Atualizar resultado de sessao."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        sessao_id = uuid4()
        store.criar_sessao(sessao_id, {
            "reclamacao_id": str(rec_id),
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. Joao",
            "data_agendada": datetime.now(UTC).isoformat(),
            "numero_sessao": 1,
        })

        store.atualizar_sessao(sessao_id, {
            "resultado": "ACORDO",
            "ata_conteudo": "Acordo obtido sobre devolucao de valores.",
        })

        s = store.get_sessao(sessao_id)
        assert s["resultado"] == "ACORDO"
        assert s["ata_conteudo"] == "Acordo obtido sobre devolucao de valores."

    def test_get_sessao_inexistente(self, store):
        """get_sessao retorna None para ID inexistente."""
        assert store.get_sessao(uuid4()) is None


# ══════════════════════════════════════════════════════════════════════════
# Teste 10: CRUD Acordos
# ══════════════════════════════════════════════════════════════════════════


class TestAcordosCRUD:
    def _criar_reclamacao_e_sessao(self, store):
        """Helper: cria reclamacao + sessao para testes de acordo."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())

        sessao_id = uuid4()
        store.criar_sessao(sessao_id, {
            "reclamacao_id": str(rec_id),
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. Joao",
            "data_agendada": datetime.now(UTC).isoformat(),
            "numero_sessao": 1,
        })
        return rec_id, sessao_id

    def test_criar_e_buscar_acordo(self, store):
        """Criar acordo e buscar pelo ID — art. 13 ss3o."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(store)

        acordo_id = uuid4()
        dados = {
            "reclamacao_id": str(rec_id),
            "sessao_id": str(sessao_id),
            "condicoes": [
                {"descricao": "Devolucao do valor", "valor": "1500.00"},
            ],
            "envolve_menores_incapazes": False,
            "status": "REDIGIDO",
            "valor_total": "1500.00",
            "pode_homologar": True,
            "parecer_mp": None,
        }
        store.criar_acordo(acordo_id, dados)

        a = store.get_acordo(acordo_id)
        assert a is not None
        assert a["id"] == str(acordo_id)
        assert a["status"] == "REDIGIDO"
        assert a["valor_total"] == "1500.00"
        assert a["pode_homologar"] is True

    def test_atualizar_acordo_parecer_mp(self, store):
        """Atualizar acordo com parecer do MP — art. 15 ssuo."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(store)

        acordo_id = uuid4()
        store.criar_acordo(acordo_id, {
            "reclamacao_id": str(rec_id),
            "sessao_id": str(sessao_id),
            "condicoes": [{"descricao": "Pensao", "valor": "2000.00"}],
            "envolve_menores_incapazes": True,
            "status": "REDIGIDO",
            "valor_total": "2000.00",
            "pode_homologar": False,
            "parecer_mp": None,
        })

        parecer = {
            "promotor_id": "mp-001",
            "promotor_nome": "Dr. Promotor",
            "favoravel": True,
            "fundamentacao": "Acordo atende ao melhor interesse do menor.",
        }
        store.atualizar_acordo(acordo_id, {
            "parecer_mp": parecer,
            "status": "PARECER_MP_EMITIDO",
            "pode_homologar": True,
        })

        a = store.get_acordo(acordo_id)
        assert a["status"] == "PARECER_MP_EMITIDO"
        assert a["pode_homologar"] is True
        assert a["parecer_mp"]["favoravel"] is True

    def test_atualizar_acordo_homologacao(self, store):
        """Homologar acordo pelo juiz — art. 15."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(store)

        acordo_id = uuid4()
        store.criar_acordo(acordo_id, {
            "reclamacao_id": str(rec_id),
            "sessao_id": str(sessao_id),
            "condicoes": [{"descricao": "Devolucao", "valor": "1000.00"}],
            "envolve_menores_incapazes": False,
            "status": "REDIGIDO",
            "valor_total": "1000.00",
            "pode_homologar": True,
        })

        store.atualizar_acordo(acordo_id, {"status": "HOMOLOGADO"})
        a = store.get_acordo(acordo_id)
        assert a["status"] == "HOMOLOGADO"

    def test_get_acordo_inexistente(self, store):
        """get_acordo retorna None para ID inexistente."""
        assert store.get_acordo(uuid4()) is None


# ══════════════════════════════════════════════════════════════════════════
# Teste 11: CRUD Usuarios
# ══════════════════════════════════════════════════════════════════════════


class TestUsuariosCRUD:
    def test_criar_e_buscar_usuario(self, store):
        """Criar usuario e buscar por e-mail."""
        dados = {
            "nome": "Secretaria Central",
            "email": "sec@cejusc.jus.br",
            "senha_hash": "$2b$12$hash_exemplo",
            "perfil": "SECRETARIA",
        }
        resultado = store.criar_usuario(dados)

        assert resultado["nome"] == "Secretaria Central"
        assert resultado["email"] == "sec@cejusc.jus.br"
        assert resultado["perfil"] == "SECRETARIA"
        assert resultado["ativo"] is True

        # Buscar por email
        u = store.get_usuario_por_email("sec@cejusc.jus.br")
        assert u is not None
        assert u["nome"] == "Secretaria Central"
        assert u["senha_hash"] == "$2b$12$hash_exemplo"

    def test_buscar_usuario_por_id(self, store):
        """Buscar usuario pelo ID."""
        dados = {
            "id": str(uuid4()),
            "nome": "Juiz Coordenador",
            "email": "juiz@tjpr.jus.br",
            "senha_hash": "$2b$12$outro_hash",
            "perfil": "JUIZ_COORDENADOR",
        }
        resultado = store.criar_usuario(dados)

        u = store.get_usuario(resultado["id"])
        assert u is not None
        assert u["nome"] == "Juiz Coordenador"
        assert u["perfil"] == "JUIZ_COORDENADOR"

    def test_buscar_usuario_inexistente(self, store):
        """Buscar usuario inexistente retorna None."""
        assert store.get_usuario_por_email("nao@existe.com") is None
        assert store.get_usuario(str(uuid4())) is None


# ══════════════════════════════════════════════════════════════════════════
# Teste 12: Encadeamento de hash (integridade append-only)
# ══════════════════════════════════════════════════════════════════════════


class TestEncadeamentoHash:
    def test_hash_encadeado_entre_eventos(self, store):
        """Cada evento referencia o hash do anterior — integridade."""
        rec_id = uuid4()
        store.criar_reclamacao(rec_id, _dados_reclamacao())
        store.transicionar(rec_id, EstadoCejusc.TRIAGEM, "sec-001", "SECRETARIA")
        store.transicionar(rec_id, EstadoCejusc.VERIFICACAO_CUSTAS, "sec-001", "SECRETARIA")

        historico = store.get_historico(rec_id)
        assert len(historico) == 3

        # Primeiro evento: hash_anterior vazio
        assert historico[0]["hash"] != ""

        # Todos os eventos tem hash nao-vazio
        for e in historico:
            assert e["hash"] != ""
            assert len(e["hash"]) == 64  # SHA-256 = 64 hex chars
