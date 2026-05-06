"""
Autenticacao e autorizacao — JWT + bcrypt.

Modulo de autenticacao do sistema Juizo · CEJUSC pre-processual.
Implementa hash de senhas com bcrypt, criacao/verificacao de tokens JWT
e dependencia FastAPI para extrair o usuario autenticado do Bearer token.

Seguranca — CLAUDE.md s7:
    Login: e-mail + senha (MVP). Em producao: biometria/ICP-Brasil.
    Tokens: JWT com expiracao curta + refresh token (futuro).
    Audit log: toda acao registrada com timestamp, ator e hash.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, ConfigDict


# ======================================================================
# Configuracao
# ======================================================================

# MVP: chave hardcoded. Em producao: variavel de ambiente (ex: os.getenv("SECRET_KEY"))
SECRET_KEY = "juizo-mvp-secret-key-trocar-em-producao"
ALGORITHM = "HS256"
TEMPO_EXPIRACAO_MINUTOS = 60


# ======================================================================
# Perfis de usuario — CLAUDE.md s6
# ======================================================================

class PerfilUsuario(str, Enum):
    """Perfis de atores processuais reconhecidos pelo sistema."""
    PARTE = "PARTE"
    ADVOGADO = "ADVOGADO"
    CONCILIADOR = "CONCILIADOR"
    MEDIADOR = "MEDIADOR"
    SECRETARIA = "SECRETARIA"
    JUIZ_COORDENADOR = "JUIZ_COORDENADOR"
    MP = "MP"


# ======================================================================
# Modelo de usuario
# ======================================================================

class UsuarioAuth(BaseModel):
    """
    Usuario autenticado no sistema.

    Representa um ator processual com credenciais de acesso.
    O perfil determina quais acoes o usuario pode executar
    na FSM do CEJUSC pre-processual.
    """
    model_config = ConfigDict(frozen=False)

    id: UUID = Field(default_factory=uuid4)
    nome: str
    email: str
    senha_hash: str
    perfil: PerfilUsuario
    ativo: bool = True
    criado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ======================================================================
# Hash de senhas — bcrypt
# ======================================================================

# Nota: usa bcrypt diretamente (passlib tem bug com Python 3.14 + bcrypt 5.x)


def hash_senha(senha: str) -> str:
    """Gera hash bcrypt da senha em texto plano."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash bcrypt."""
    return bcrypt.checkpw(
        senha_plana.encode("utf-8"),
        senha_hash.encode("utf-8"),
    )


# ======================================================================
# Tokens JWT
# ======================================================================

def criar_token_acesso(dados: dict[str, Any], expiracao: timedelta | None = None) -> str:
    """
    Cria token JWT com os dados fornecidos.

    Payload padrao inclui: sub (email), perfil, nome, exp.
    """
    payload = dados.copy()
    if expiracao is None:
        expiracao = timedelta(minutes=TEMPO_EXPIRACAO_MINUTOS)
    payload["exp"] = datetime.now(UTC) + expiracao
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict[str, Any]:
    """
    Decodifica e valida um token JWT.

    Raises:
        HTTPException 401 se o token for invalido ou expirado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido: campo 'sub' ausente",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ======================================================================
# Dependencia FastAPI — extrair usuario do Bearer token
# ======================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Store de usuarios in-memory (MVP) — referenciado pelas rotas
# Em producao: PostgreSQL + SQLModel
_usuarios: dict[str, UsuarioAuth] = {}


def get_store_usuarios() -> dict[str, UsuarioAuth]:
    """Retorna o store de usuarios (singleton no MVP)."""
    return _usuarios


async def get_usuario_atual(
    token: str = Depends(oauth2_scheme),
    usuarios: dict[str, UsuarioAuth] = Depends(get_store_usuarios),
) -> UsuarioAuth:
    """
    Dependencia FastAPI que extrai o usuario autenticado do Bearer token.

    Valida o token JWT, localiza o usuario no store e verifica se esta ativo.

    Raises:
        HTTPException 401 se token invalido ou usuario nao encontrado.
        HTTPException 403 se usuario esta inativo.
    """
    payload = verificar_token(token)
    email = payload["sub"]

    usuario = usuarios.get(email)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario nao encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inativo",
        )

    return usuario
