"""
Testes da API — CEJUSC pré-processual.

Testa todos os endpoints: CRUD, transições FSM, sessões,
acordos, automações e health checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.store import EventStore
from api.deps import get_store


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _store_limpo():
    """Cria um store limpo para cada teste."""
    test_store = EventStore()

    def _override():
        return test_store

    app.dependency_overrides[get_store] = _override
    yield test_store
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Cliente de teste FastAPI."""
    return TestClient(app)


def _reclamacao_payload() -> dict:
    """Payload padrão para criar reclamação — art. 9º."""
    return {
        "cejusc_destino": "CEJUSC-CENTRAL-CURITIBA",
        "reclamante": {
            "nome": "Maria Silva",
            "tipo_pessoa": "FISICA",
            "cpf": "12345678901",
            "email": "maria@email.com",
            "telefone": "(41)99999-0001",
            "endereco": {
                "logradouro": "Rua XV de Novembro",
                "numero": "100",
                "bairro": "Centro",
                "cidade": "Curitiba",
                "uf": "PR",
                "cep": "80020-310",
            },
        },
        "reclamado": {
            "nome": "Empresa XYZ Ltda",
            "tipo_pessoa": "JURIDICA",
            "cnpj": "12345678000195",
            "email": "contato@xyz.com",
            "telefone": "(41)3333-0001",
            "endereco": {
                "logradouro": "Av. Sete de Setembro",
                "numero": "2000",
                "bairro": "Centro",
                "cidade": "Curitiba",
                "uf": "PR",
                "cep": "80060-070",
            },
        },
        "fatos": "Compra de produto com defeito sem resolução pelo SAC da empresa.",
        "pedidos": [
            {"descricao": "Devolução do valor pago", "valor": "1500.00"},
            {"descricao": "Indenização por danos morais", "valor": "3000.00"},
        ],
        "valor_causa": "4500.00",
        "modalidade": "CONCILIACAO",
        "opcao_custas": "TAXA_PAGA",
    }


# ══════════════════════════════════════════════════════════════════════════
# Health checks
# ══════════════════════════════════════════════════════════════════════════


class TestHealthCheck:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sistema"] == "Juízo · Sistema de Informação Jurisdicional"
        assert data["modulo"] == "CEJUSC Pré-Processual"

    def test_saude(self, client):
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operacional"
        assert "contadores" in data


# ══════════════════════════════════════════════════════════════════════════
# Reclamações — CRUD
# ══════════════════════════════════════════════════════════════════════════


class TestReclamacoesCRUD:
    def test_criar_reclamacao(self, client):
        """art. 9º — Protocolar reclamação com todos os requisitos."""
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["cejusc_destino"] == "CEJUSC-CENTRAL-CURITIBA"
        assert data["estado_atual"] == "SOLICITACAO_RECEBIDA"
        assert data["reclamante"]["nome"] == "Maria Silva"
        assert data["reclamado"]["nome"] == "Empresa XYZ Ltda"
        assert data["protocolado_em"] is not None

    def test_listar_reclamacoes(self, client):
        # Criar duas reclamações
        client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())

        resp = client.get("/api/v1/reclamacoes/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_reclamacao(self, client):
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        rec_id = resp.json()["id"]

        resp = client.get(f"/api/v1/reclamacoes/{rec_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rec_id

    def test_get_reclamacao_inexistente(self, client):
        resp = client.get("/api/v1/reclamacoes/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_validacao_fatos_minimo(self, client):
        """art. 9º — fatos deve ter no mínimo 10 caracteres."""
        payload = _reclamacao_payload()
        payload["fatos"] = "curto"
        resp = client.post("/api/v1/reclamacoes/", json=payload)
        assert resp.status_code == 422

    def test_validacao_pedidos_obrigatorios(self, client):
        """art. 9º — deve ter ao menos um pedido."""
        payload = _reclamacao_payload()
        payload["pedidos"] = []
        resp = client.post("/api/v1/reclamacoes/", json=payload)
        assert resp.status_code == 422

    def test_validacao_valor_causa(self, client):
        """art. 9º — valor da causa deve ser > 0."""
        payload = _reclamacao_payload()
        payload["valor_causa"] = "0"
        resp = client.post("/api/v1/reclamacoes/", json=payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# Transições FSM
# ══════════════════════════════════════════════════════════════════════════


class TestTransicoesFSM:
    def _criar_reclamacao(self, client) -> str:
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        return resp.json()["id"]

    def test_transicao_valida(self, client):
        """SOLICITACAO_RECEBIDA → TRIAGEM (SECRETARIA)."""
        rec_id = self._criar_reclamacao(client)

        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_anterior"] == "SOLICITACAO_RECEBIDA"
        assert data["estado_novo"] == "TRIAGEM"
        assert data["hash"] != ""

    def test_transicao_invalida(self, client):
        """SOLICITACAO_RECEBIDA → HOMOLOGADO (inválida)."""
        rec_id = self._criar_reclamacao(client)

        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "HOMOLOGADO",
            "ator_id": "juiz-001",
            "ator_tipo": "JUIZ_COORDENADOR",
        })
        assert resp.status_code == 422
        assert resp.json()["detail"]["status"] == "TRANSICAO_INVALIDA"

    def test_ator_nao_autorizado(self, client):
        """SOLICITACAO_RECEBIDA → TRIAGEM (PARTE — não autorizado)."""
        rec_id = self._criar_reclamacao(client)

        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "parte-001",
            "ator_tipo": "PARTE",
        })
        assert resp.status_code == 403
        assert resp.json()["detail"]["status"] == "ATOR_NAO_AUTORIZADO"

    def test_fluxo_completo_ate_cadastrado(self, client):
        """Happy path: RECEBIDA → TRIAGEM → VERIFICACAO_CUSTAS → CADASTRADO."""
        rec_id = self._criar_reclamacao(client)

        # → TRIAGEM
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })

        # → VERIFICACAO_CUSTAS
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "VERIFICACAO_CUSTAS",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })

        # → CADASTRADO
        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "CADASTRADO",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })
        assert resp.status_code == 200
        assert resp.json()["estado_novo"] == "CADASTRADO"

    def test_estado_endpoint(self, client):
        rec_id = self._criar_reclamacao(client)

        resp = client.get(f"/api/v1/reclamacoes/{rec_id}/estado")
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_atual"] == "SOLICITACAO_RECEBIDA"
        assert "TRIAGEM" in data["transicoes_validas"]
        assert data["is_terminal"] is False

    def test_historico_endpoint(self, client):
        rec_id = self._criar_reclamacao(client)

        # Fazer uma transição
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })

        resp = client.get(f"/api/v1/reclamacoes/{rec_id}/historico")
        assert resp.status_code == 200
        historico = resp.json()
        assert len(historico) == 2  # criação + transição
        assert historico[0]["estado_novo"] == "SOLICITACAO_RECEBIDA"
        assert historico[1]["estado_novo"] == "TRIAGEM"

    def test_estado_terminal_bloqueia_transicao(self, client):
        """Arquivamento é estado terminal — nenhuma transição possível."""
        rec_id = self._criar_reclamacao(client)

        # → TRIAGEM → ARQUIVADO_INCOMPETENTE
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "ARQUIVADO_INCOMPETENTE",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })

        # Tentar transição a partir de terminal
        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })
        assert resp.status_code == 422
        assert resp.json()["detail"]["status"] == "ESTADO_TERMINAL"


# ══════════════════════════════════════════════════════════════════════════
# Sessões
# ══════════════════════════════════════════════════════════════════════════


class TestSessoes:
    def _criar_reclamacao(self, client) -> str:
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        return resp.json()["id"]

    def test_criar_sessao(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        resp = client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João Mediador",
            "data_agendada": data_sessao,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["reclamacao_id"] == rec_id
        assert data["conciliador_nome"] == "Dr. João Mediador"
        assert data["numero_sessao"] == 1

    def test_listar_sessoes(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João",
            "data_agendada": data_sessao,
        })

        resp = client.get("/api/v1/sessoes/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_listar_sessoes_por_reclamacao(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        # Criar 2 sessões para mesma reclamação
        for i in range(2):
            client.post("/api/v1/sessoes/", json={
                "reclamacao_id": rec_id,
                "conciliador_id": "conc-001",
                "conciliador_nome": "Dr. João",
                "data_agendada": data_sessao,
            })

        resp = client.get(f"/api/v1/sessoes/?reclamacao_id={rec_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[1]["numero_sessao"] == 2

    def test_get_sessao(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        resp = client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João",
            "data_agendada": data_sessao,
        })
        sessao_id = resp.json()["id"]

        resp = client.get(f"/api/v1/sessoes/{sessao_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sessao_id

    def test_registrar_resultado_acordo(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        resp = client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João",
            "data_agendada": data_sessao,
        })
        sessao_id = resp.json()["id"]

        resp = client.post(f"/api/v1/sessoes/{sessao_id}/resultado", json={
            "resultado": "ACORDO",
            "ata_conteudo": "As partes chegaram a um acordo sobre os valores devidos.",
            "reclamante_presente": True,
            "reclamado_presente": True,
        })
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "ACORDO"

    def test_registrar_resultado_sem_acordo(self, client):
        rec_id = self._criar_reclamacao(client)
        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        resp = client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João",
            "data_agendada": data_sessao,
        })
        sessao_id = resp.json()["id"]

        resp = client.post(f"/api/v1/sessoes/{sessao_id}/resultado", json={
            "resultado": "SEM_ACORDO",
            "ata_conteudo": "As partes não chegaram a um consenso sobre os valores.",
            "reclamante_presente": True,
            "reclamado_presente": True,
        })
        assert resp.status_code == 200
        assert resp.json()["resultado"] == "SEM_ACORDO"

    def test_sessao_inexistente(self, client):
        resp = client.get("/api/v1/sessoes/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# Acordos
# ══════════════════════════════════════════════════════════════════════════


class TestAcordos:
    def _criar_reclamacao_e_sessao(self, client):
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        rec_id = resp.json()["id"]

        data_sessao = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        resp = client.post("/api/v1/sessoes/", json={
            "reclamacao_id": rec_id,
            "conciliador_id": "conc-001",
            "conciliador_nome": "Dr. João",
            "data_agendada": data_sessao,
        })
        sessao_id = resp.json()["id"]

        return rec_id, sessao_id

    def test_criar_acordo(self, client):
        """art. 13 §3º — Registrar acordo com condições."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Devolução do valor pago",
                    "parte_responsavel": "Empresa XYZ",
                    "valor": "1500.00",
                    "forma_pagamento": "PIX em 5 dias úteis",
                },
            ],
            "envolve_menores_incapazes": False,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "REDIGIDO"
        assert data["pode_homologar"] is True
        assert data["valor_total"] == "1500.00"

    def test_acordo_com_menores_requer_mp(self, client):
        """art. 15 §ú — Acordo com menores requer parecer do MP."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Pensão alimentícia",
                    "parte_responsavel": "João Silva",
                    "valor": "2000.00",
                },
            ],
            "envolve_menores_incapazes": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["envolve_menores_incapazes"] is True
        assert data["pode_homologar"] is False  # Precisa MP

    def test_parecer_mp_favoravel(self, client):
        """art. 15 §ú — Parecer favorável libera homologação."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Pensão alimentícia",
                    "parte_responsavel": "João",
                    "valor": "2000.00",
                },
            ],
            "envolve_menores_incapazes": True,
        })
        acordo_id = resp.json()["id"]

        resp = client.post(f"/api/v1/acordos/{acordo_id}/parecer-mp", json={
            "promotor_id": "mp-001",
            "promotor_nome": "Dr. Promotor da Silva",
            "favoravel": True,
            "fundamentacao": "O acordo atende ao melhor interesse do menor, conforme art. 227 CF.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PARECER_MP_EMITIDO"
        assert data["pode_homologar"] is True

    def test_parecer_mp_desfavoravel(self, client):
        """art. 15 §ú — Parecer desfavorável bloqueia homologação."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Pensão alimentícia",
                    "parte_responsavel": "João",
                    "valor": "200.00",
                },
            ],
            "envolve_menores_incapazes": True,
        })
        acordo_id = resp.json()["id"]

        resp = client.post(f"/api/v1/acordos/{acordo_id}/parecer-mp", json={
            "promotor_id": "mp-001",
            "promotor_nome": "Dr. Promotor",
            "favoravel": False,
            "fundamentacao": "O valor proposto é insuficiente para atender as necessidades do menor.",
        })
        assert resp.status_code == 200
        assert resp.json()["pode_homologar"] is False

    def test_parecer_mp_sem_menores_recusado(self, client):
        """Parecer MP não é necessário quando não há menores."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Devolução",
                    "parte_responsavel": "Empresa",
                    "valor": "1000.00",
                },
            ],
            "envolve_menores_incapazes": False,
        })
        acordo_id = resp.json()["id"]

        resp = client.post(f"/api/v1/acordos/{acordo_id}/parecer-mp", json={
            "promotor_id": "mp-001",
            "promotor_nome": "Dr. Promotor",
            "favoravel": True,
            "fundamentacao": "Parecer não necessário",
        })
        assert resp.status_code == 422

    def test_homologar_acordo(self, client):
        """art. 15 — Homologação pelo juiz coordenador."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Devolução do valor",
                    "parte_responsavel": "Empresa XYZ",
                    "valor": "1500.00",
                },
            ],
            "envolve_menores_incapazes": False,
        })
        acordo_id = resp.json()["id"]

        resp = client.post(
            f"/api/v1/acordos/{acordo_id}/homologar"
            "?juiz_id=juiz-001&juiz_nome=Dr.%20Juiz%20Coordenador"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "HOMOLOGADO"

    def test_homologar_sem_mp_bloqueado(self, client):
        """Não pode homologar acordo com menores sem parecer MP."""
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Pensão",
                    "parte_responsavel": "Pai",
                    "valor": "2000.00",
                },
            ],
            "envolve_menores_incapazes": True,
        })
        acordo_id = resp.json()["id"]

        resp = client.post(
            f"/api/v1/acordos/{acordo_id}/homologar"
            "?juiz_id=juiz-001&juiz_nome=Dr.%20Juiz"
        )
        assert resp.status_code == 422

    def test_get_acordo(self, client):
        rec_id, sessao_id = self._criar_reclamacao_e_sessao(client)

        resp = client.post("/api/v1/acordos/", json={
            "reclamacao_id": rec_id,
            "sessao_id": sessao_id,
            "condicoes": [
                {
                    "descricao": "Devolução",
                    "parte_responsavel": "Empresa",
                    "valor": "500.00",
                },
            ],
        })
        acordo_id = resp.json()["id"]

        resp = client.get(f"/api/v1/acordos/{acordo_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == acordo_id

    def test_acordo_inexistente(self, client):
        resp = client.get("/api/v1/acordos/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# Automações
# ══════════════════════════════════════════════════════════════════════════


class TestAutomacoes:
    def _criar_reclamacao(self, client) -> str:
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        return resp.json()["id"]

    def test_carta_convite(self, client):
        """art. 10º III/IV — Gerar carta-convite ao reclamado."""
        rec_id = self._criar_reclamacao(client)

        resp = client.get(f"/api/v1/automacoes/{rec_id}/carta-convite")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reclamacao_id"] == rec_id
        assert "Empresa XYZ" in data["destinatario"]
        assert "CARTA-CONVITE" in data["conteudo"]
        assert "art. 4º" in data["conteudo"]

    def test_certidao_negativa(self, client):
        """art. 12 §3º — Gerar certidão negativa."""
        rec_id = self._criar_reclamacao(client)

        resp = client.get(f"/api/v1/automacoes/{rec_id}/certidao-negativa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reclamacao_id"] == rec_id
        assert "CERTIDÃO NEGATIVA" in data["conteudo"]
        assert "NÃO induziu prevenção" in data["conteudo"]

    def test_prazos(self, client):
        """art. 9º §2º, art. 14 — Calcular prazos legais."""
        rec_id = self._criar_reclamacao(client)

        resp = client.get(f"/api/v1/automacoes/{rec_id}/prazos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reclamacao_id"] == rec_id
        assert data["prazo_regularizacao"] is not None

    def test_automacoes_reclamacao_inexistente(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        for endpoint in ["carta-convite", "certidao-negativa", "prazos"]:
            resp = client.get(f"/api/v1/automacoes/{fake_id}/{endpoint}")
            assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# Fluxo completo (happy path)
# ══════════════════════════════════════════════════════════════════════════


class TestFluxoCompleto:
    def test_happy_path_com_acordo(self, client):
        """
        Fluxo completo com acordo — happy path:
        RECEBIDA → TRIAGEM → CUSTAS → CADASTRADO → AGENDADA →
        NOTIFICACOES → CONDUZIDA → ACORDO_REDIGIDO → CONCLUSO_JUIZ →
        HOMOLOGADO → ARQUIVADO_ACORDO
        """
        # 1. Protocolar reclamação
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        assert resp.status_code == 201
        rec_id = resp.json()["id"]

        transicoes = [
            ("TRIAGEM", "sec-001", "SECRETARIA"),
            ("VERIFICACAO_CUSTAS", "sec-001", "SECRETARIA"),
            ("CADASTRADO", "sec-001", "SECRETARIA"),
            ("SESSAO_AGENDADA", "sec-001", "SECRETARIA"),
            ("NOTIFICACOES_ENVIADAS", "sec-001", "SECRETARIA"),
            ("SESSAO_CONDUZIDA", "conc-001", "CONCILIADOR"),
            ("ACORDO_REDIGIDO", "conc-001", "CONCILIADOR"),
            ("CONCLUSO_JUIZ", "sec-001", "SECRETARIA"),
            ("HOMOLOGADO", "juiz-001", "JUIZ_COORDENADOR"),
            ("ARQUIVADO_ACORDO", "sec-001", "SECRETARIA"),
        ]

        for estado_destino, ator_id, ator_tipo in transicoes:
            resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
                "estado_destino": estado_destino,
                "ator_id": ator_id,
                "ator_tipo": ator_tipo,
            })
            assert resp.status_code == 200, (
                f"Falha na transição para {estado_destino}: {resp.json()}"
            )

        # Verificar estado final
        resp = client.get(f"/api/v1/reclamacoes/{rec_id}/estado")
        assert resp.json()["estado_atual"] == "ARQUIVADO_ACORDO"
        assert resp.json()["is_terminal"] is True
        assert resp.json()["transicoes_validas"] == []

        # Verificar histórico completo
        resp = client.get(f"/api/v1/reclamacoes/{rec_id}/historico")
        historico = resp.json()
        assert len(historico) == 11  # criação + 10 transições

    def test_fluxo_arquivamento_incompetente(self, client):
        """Fluxo de arquivamento por incompetência na triagem."""
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        rec_id = resp.json()["id"]

        # → TRIAGEM
        client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "TRIAGEM",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })

        # → ARQUIVADO_INCOMPETENTE
        resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
            "estado_destino": "ARQUIVADO_INCOMPETENTE",
            "ator_id": "sec-001",
            "ator_tipo": "SECRETARIA",
        })
        assert resp.status_code == 200

        # Verificar terminal
        resp = client.get(f"/api/v1/reclamacoes/{rec_id}/estado")
        assert resp.json()["is_terminal"] is True

    def test_fluxo_com_mp(self, client):
        """
        Fluxo com parecer do MP — menores/incapazes:
        ACORDO_REDIGIDO → AGUARDANDO_MP → CONCLUSO_JUIZ → HOMOLOGADO
        """
        resp = client.post("/api/v1/reclamacoes/", json=_reclamacao_payload())
        rec_id = resp.json()["id"]

        transicoes_pre_acordo = [
            ("TRIAGEM", "sec-001", "SECRETARIA"),
            ("VERIFICACAO_CUSTAS", "sec-001", "SECRETARIA"),
            ("CADASTRADO", "sec-001", "SECRETARIA"),
            ("SESSAO_AGENDADA", "sec-001", "SECRETARIA"),
            ("NOTIFICACOES_ENVIADAS", "sec-001", "SECRETARIA"),
            ("SESSAO_CONDUZIDA", "conc-001", "CONCILIADOR"),
            ("ACORDO_REDIGIDO", "conc-001", "CONCILIADOR"),
            ("AGUARDANDO_MP", "sec-001", "SECRETARIA"),  # Envolve menores
            ("CONCLUSO_JUIZ", "sec-001", "SECRETARIA"),
            ("HOMOLOGADO", "juiz-001", "JUIZ_COORDENADOR"),
        ]

        for estado_destino, ator_id, ator_tipo in transicoes_pre_acordo:
            resp = client.post(f"/api/v1/reclamacoes/{rec_id}/transicao", json={
                "estado_destino": estado_destino,
                "ator_id": ator_id,
                "ator_tipo": ator_tipo,
            })
            assert resp.status_code == 200, (
                f"Falha em {estado_destino}: {resp.json()}"
            )
