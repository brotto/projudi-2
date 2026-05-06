"""
Rotas de autenticacao — CEJUSC pre-processual.

Registro, login e consulta de usuario autenticado.
Store in-memory para MVP — em producao: PostgreSQL + SQLModel.

Perfis reconhecidos (CLAUDE.md s6):
    PARTE, ADVOGADO, CONCILIADOR, MEDIADOR,
    SECRETARIA, JUIZ_COORDENADOR, MP
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.auth import (
    PerfilUsuario,
    UsuarioAuth,
    criar_token_acesso,
    get_store_usuarios,
    get_usuario_atual,
    hash_senha,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


# ======================================================================
# Schemas de request/response
# ======================================================================

class RegistroIn(BaseModel):
    """Request body para registro de novo usuario."""
    nome: str = Field(min_length=1, description="Nome completo do usuario")
    email: str = Field(min_length=1, description="E-mail (sera usado como login)")
    senha: str = Field(min_length=6, description="Senha (minimo 6 caracteres)")
    perfil: PerfilUsuario = Field(description="Perfil do ator processual")

    @field_validator("email")
    @classmethod
    def email_deve_conter_arroba(cls, v: str) -> str:
        """Validacao basica de formato de e-mail."""
        if "@" not in v:
            raise ValueError("E-mail deve conter @")
        return v.strip().lower()


class LoginIn(BaseModel):
    """Request body para login."""
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenOut(BaseModel):
    """Response de login — token JWT."""
    access_token: str
    token_type: str = "bearer"


class UsuarioOut(BaseModel):
    """Response de usuario (sem senha)."""
    id: str
    nome: str
    email: str
    perfil: str
    ativo: bool


class RegistroOut(BaseModel):
    """Response de registro — usuario criado + token."""
    usuario: UsuarioOut
    access_token: str
    token_type: str = "bearer"


# ======================================================================
# Rotas
# ======================================================================


@router.post(
    "/registrar",
    response_model=RegistroOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuario",
)
def registrar(
    body: RegistroIn,
    usuarios: dict[str, UsuarioAuth] = Depends(get_store_usuarios),
) -> RegistroOut:
    """
    Cria um novo usuario no sistema.

    Validacoes:
    - E-mail deve ser unico
    - Senha minimo 6 caracteres
    - Perfil deve ser um dos reconhecidos pelo sistema
    """
    # Verificar unicidade de e-mail
    if body.email in usuarios:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail ja cadastrado",
        )

    # Criar usuario com senha hasheada
    usuario = UsuarioAuth(
        nome=body.nome,
        email=body.email,
        senha_hash=hash_senha(body.senha),
        perfil=body.perfil,
    )

    # Persistir no store in-memory
    usuarios[body.email] = usuario

    # Gerar token JWT para o novo usuario
    token = criar_token_acesso({
        "sub": usuario.email,
        "perfil": usuario.perfil.value,
        "nome": usuario.nome,
    })

    return RegistroOut(
        usuario=UsuarioOut(
            id=str(usuario.id),
            nome=usuario.nome,
            email=usuario.email,
            perfil=usuario.perfil.value,
            ativo=usuario.ativo,
        ),
        access_token=token,
    )


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Login — obter token JWT",
)
def login(
    body: LoginIn,
    usuarios: dict[str, UsuarioAuth] = Depends(get_store_usuarios),
) -> TokenOut:
    """
    Autentica usuario com e-mail + senha e retorna token JWT.

    O token inclui: sub (email), perfil, nome, exp (60 min).
    """
    usuario = usuarios.get(body.email)

    if usuario is None or not verificar_senha(body.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inativo",
        )

    token = criar_token_acesso({
        "sub": usuario.email,
        "perfil": usuario.perfil.value,
        "nome": usuario.nome,
    })

    return TokenOut(access_token=token)


@router.get(
    "/me",
    response_model=UsuarioOut,
    summary="Consultar usuario autenticado",
)
def me(
    usuario: UsuarioAuth = Depends(get_usuario_atual),
) -> UsuarioOut:
    """
    Retorna os dados do usuario autenticado.

    Endpoint protegido — requer Bearer token valido no header Authorization.
    """
    return UsuarioOut(
        id=str(usuario.id),
        nome=usuario.nome,
        email=usuario.email,
        perfil=usuario.perfil.value,
        ativo=usuario.ativo,
    )
