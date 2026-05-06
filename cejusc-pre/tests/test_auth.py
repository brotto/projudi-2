"""
Testes de autenticacao — CEJUSC pre-processual.

Testa registro, login, endpoints protegidos e validacao de perfis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import get_store_usuarios, UsuarioAuth


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def _store_usuarios_limpo():
    """Limpa o store de usuarios antes de cada teste."""
    test_store: dict[str, UsuarioAuth] = {}

    def _override():
        return test_store

    app.dependency_overrides[get_store_usuarios] = _override
    yield test_store
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Cliente de teste FastAPI."""
    return TestClient(app)


def _registro_payload(
    nome: str = "Maria Silva",
    email: str = "maria@email.com",
    senha: str = "senha123",
    perfil: str = "SECRETARIA",
) -> dict:
    """Payload padrao para registro de usuario."""
    return {
        "nome": nome,
        "email": email,
        "senha": senha,
        "perfil": perfil,
    }


def _registrar_e_logar(client: TestClient, **kwargs) -> str:
    """Registra usuario e retorna o token JWT."""
    payload = _registro_payload(**kwargs)
    resp = client.post("/api/v1/auth/registrar", json=payload)
    assert resp.status_code == 201
    return resp.json()["access_token"]


# ======================================================================
# Registro
# ======================================================================


class TestRegistro:
    def test_registrar_usuario(self, client):
        """Registro com dados validos retorna 201 + token."""
        resp = client.post("/api/v1/auth/registrar", json=_registro_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["usuario"]["nome"] == "Maria Silva"
        assert data["usuario"]["email"] == "maria@email.com"
        assert data["usuario"]["perfil"] == "SECRETARIA"
        assert data["usuario"]["ativo"] is True
        assert data["access_token"] != ""
        assert data["token_type"] == "bearer"

    def test_registrar_email_duplicado(self, client):
        """Registro com e-mail ja cadastrado retorna 409."""
        client.post("/api/v1/auth/registrar", json=_registro_payload())
        resp = client.post("/api/v1/auth/registrar", json=_registro_payload())
        assert resp.status_code == 409
        assert "ja cadastrado" in resp.json()["detail"]

    def test_registrar_senha_curta(self, client):
        """Senha com menos de 6 caracteres retorna 422."""
        payload = _registro_payload(senha="123")
        resp = client.post("/api/v1/auth/registrar", json=payload)
        assert resp.status_code == 422

    def test_registrar_email_invalido(self, client):
        """E-mail sem @ retorna 422."""
        payload = _registro_payload(email="email-invalido")
        resp = client.post("/api/v1/auth/registrar", json=payload)
        assert resp.status_code == 422

    def test_registrar_perfil_invalido(self, client):
        """Perfil nao reconhecido pelo sistema retorna 422."""
        payload = _registro_payload(perfil="ADMINISTRADOR")
        resp = client.post("/api/v1/auth/registrar", json=payload)
        assert resp.status_code == 422

    def test_registrar_todos_os_perfis(self, client):
        """Todos os 7 perfis reconhecidos podem ser registrados."""
        perfis = [
            "PARTE",
            "ADVOGADO",
            "CONCILIADOR",
            "MEDIADOR",
            "SECRETARIA",
            "JUIZ_COORDENADOR",
            "MP",
        ]
        for i, perfil in enumerate(perfis):
            payload = _registro_payload(
                nome=f"Usuario {perfil}",
                email=f"usuario{i}@email.com",
                perfil=perfil,
            )
            resp = client.post("/api/v1/auth/registrar", json=payload)
            assert resp.status_code == 201, (
                f"Falha ao registrar perfil {perfil}: {resp.json()}"
            )
            assert resp.json()["usuario"]["perfil"] == perfil

    def test_registrar_email_normalizado(self, client):
        """E-mail e salvo em lowercase e sem espacos."""
        payload = _registro_payload(email="  MARIA@Email.COM  ")
        resp = client.post("/api/v1/auth/registrar", json=payload)
        assert resp.status_code == 201
        assert resp.json()["usuario"]["email"] == "maria@email.com"


# ======================================================================
# Login
# ======================================================================


class TestLogin:
    def test_login_sucesso(self, client):
        """Login com credenciais corretas retorna token JWT."""
        client.post("/api/v1/auth/registrar", json=_registro_payload())

        resp = client.post("/api/v1/auth/login", json={
            "email": "maria@email.com",
            "senha": "senha123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] != ""
        assert data["token_type"] == "bearer"

    def test_login_senha_errada(self, client):
        """Login com senha incorreta retorna 401."""
        client.post("/api/v1/auth/registrar", json=_registro_payload())

        resp = client.post("/api/v1/auth/login", json={
            "email": "maria@email.com",
            "senha": "senha_errada",
        })
        assert resp.status_code == 401
        assert "incorretos" in resp.json()["detail"]

    def test_login_email_inexistente(self, client):
        """Login com e-mail nao cadastrado retorna 401."""
        resp = client.post("/api/v1/auth/login", json={
            "email": "naoexiste@email.com",
            "senha": "senha123",
        })
        assert resp.status_code == 401

    def test_login_email_normalizado(self, client):
        """Login funciona com e-mail em diferentes cases."""
        client.post("/api/v1/auth/registrar", json=_registro_payload())

        resp = client.post("/api/v1/auth/login", json={
            "email": "MARIA@EMAIL.COM",
            "senha": "senha123",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"] != ""


# ======================================================================
# Endpoint protegido (/me)
# ======================================================================


class TestEndpointProtegido:
    def test_me_com_token_valido(self, client):
        """GET /auth/me com token valido retorna dados do usuario."""
        token = _registrar_e_logar(client)

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nome"] == "Maria Silva"
        assert data["email"] == "maria@email.com"
        assert data["perfil"] == "SECRETARIA"
        assert data["ativo"] is True
        # Senha NUNCA deve aparecer na resposta
        assert "senha" not in data
        assert "senha_hash" not in data

    def test_me_sem_token(self, client):
        """GET /auth/me sem token retorna 401."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_com_token_invalido(self, client):
        """GET /auth/me com token invalido retorna 401."""
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer token-falso-invalido"},
        )
        assert resp.status_code == 401

    def test_me_com_token_de_login(self, client):
        """Token obtido via login funciona no endpoint protegido."""
        client.post("/api/v1/auth/registrar", json=_registro_payload())

        resp_login = client.post("/api/v1/auth/login", json={
            "email": "maria@email.com",
            "senha": "senha123",
        })
        token = resp_login.json()["access_token"]

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "maria@email.com"

    def test_me_cada_perfil(self, client):
        """Todos os perfis podem acessar o endpoint /me."""
        perfis = [
            "PARTE",
            "ADVOGADO",
            "CONCILIADOR",
            "MEDIADOR",
            "SECRETARIA",
            "JUIZ_COORDENADOR",
            "MP",
        ]
        for i, perfil in enumerate(perfis):
            token = _registrar_e_logar(
                client,
                nome=f"Usuario {perfil}",
                email=f"user{i}@email.com",
                perfil=perfil,
            )
            resp = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, (
                f"Falha no /me para perfil {perfil}: {resp.json()}"
            )
            assert resp.json()["perfil"] == perfil


# ======================================================================
# Funcoes utilitarias de auth (unit tests)
# ======================================================================


class TestAuthUtils:
    def test_hash_senha_diferente_da_original(self):
        """Hash bcrypt nao e igual a senha original."""
        from api.auth import hash_senha
        senha = "minha_senha_123"
        hashed = hash_senha(senha)
        assert hashed != senha
        assert len(hashed) > 20

    def test_verificar_senha_correta(self):
        """verificar_senha retorna True para senha correta."""
        from api.auth import hash_senha, verificar_senha
        senha = "minha_senha_123"
        hashed = hash_senha(senha)
        assert verificar_senha(senha, hashed) is True

    def test_verificar_senha_incorreta(self):
        """verificar_senha retorna False para senha incorreta."""
        from api.auth import hash_senha, verificar_senha
        hashed = hash_senha("senha_certa")
        assert verificar_senha("senha_errada", hashed) is False

    def test_criar_e_verificar_token(self):
        """Token criado pode ser decodificado com os dados corretos."""
        from api.auth import criar_token_acesso, verificar_token
        dados = {"sub": "teste@email.com", "perfil": "SECRETARIA", "nome": "Teste"}
        token = criar_token_acesso(dados)
        payload = verificar_token(token)
        assert payload["sub"] == "teste@email.com"
        assert payload["perfil"] == "SECRETARIA"
        assert payload["nome"] == "Teste"
        assert "exp" in payload

    def test_token_expirado(self):
        """Token expirado levanta HTTPException 401."""
        from datetime import timedelta
        from fastapi import HTTPException
        from api.auth import criar_token_acesso, verificar_token

        token = criar_token_acesso(
            {"sub": "teste@email.com"},
            expiracao=timedelta(seconds=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            verificar_token(token)
        assert exc_info.value.status_code == 401
