"""
Modelos base de partes processuais.

Define os tipos fundamentais de participantes em qualquer processo:
- Endereco: endereço completo
- Parte: participante do processo (pessoa física ou jurídica)
- Advogado: representante legal com OAB
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
import re


class TipoPessoa(str, Enum):
    """Tipo de pessoa — física ou jurídica."""
    FISICA = "FISICA"
    JURIDICA = "JURIDICA"


class UF(str, Enum):
    """Unidades da Federação do Brasil."""
    AC = "AC"
    AL = "AL"
    AP = "AP"
    AM = "AM"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MT = "MT"
    MS = "MS"
    MG = "MG"
    PA = "PA"
    PB = "PB"
    PR = "PR"
    PE = "PE"
    PI = "PI"
    RJ = "RJ"
    RN = "RN"
    RS = "RS"
    RO = "RO"
    RR = "RR"
    SC = "SC"
    SP = "SP"
    SE = "SE"
    TO = "TO"


class Endereco(BaseModel):
    """Endereço completo conforme padrão dos Correios."""
    logradouro: str = Field(min_length=1)
    numero: str = Field(min_length=1)
    complemento: str = ""
    bairro: str = Field(min_length=1)
    cidade: str = Field(min_length=1)
    uf: UF
    cep: str = Field(min_length=8, max_length=9)

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, v: str) -> str:
        limpo = re.sub(r"[^0-9]", "", v)
        if len(limpo) != 8:
            raise ValueError("CEP deve conter exatamente 8 dígitos")
        return f"{limpo[:5]}-{limpo[5:]}"


def validar_cpf(cpf: str) -> str:
    """Valida e formata CPF (11 dígitos, algoritmo de verificação)."""
    limpo = re.sub(r"[^0-9]", "", cpf)
    if len(limpo) != 11:
        raise ValueError("CPF deve conter exatamente 11 dígitos")
    # Rejeita sequências repetidas
    if limpo == limpo[0] * 11:
        raise ValueError("CPF inválido")
    # Dígito verificador 1
    soma = sum(int(limpo[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(limpo[9]) != d1:
        raise ValueError("CPF inválido — dígito verificador incorreto")
    # Dígito verificador 2
    soma = sum(int(limpo[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    if int(limpo[10]) != d2:
        raise ValueError("CPF inválido — dígito verificador incorreto")
    return f"{limpo[:3]}.{limpo[3:6]}.{limpo[6:9]}-{limpo[9:]}"


def validar_cnpj(cnpj: str) -> str:
    """Valida e formata CNPJ (14 dígitos, algoritmo de verificação)."""
    limpo = re.sub(r"[^0-9]", "", cnpj)
    if len(limpo) != 14:
        raise ValueError("CNPJ deve conter exatamente 14 dígitos")
    if limpo == limpo[0] * 14:
        raise ValueError("CNPJ inválido")
    # Dígito verificador 1
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(limpo[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(limpo[12]) != d1:
        raise ValueError("CNPJ inválido — dígito verificador incorreto")
    # Dígito verificador 2
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(limpo[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    if int(limpo[13]) != d2:
        raise ValueError("CNPJ inválido — dígito verificador incorreto")
    return f"{limpo[:2]}.{limpo[2:5]}.{limpo[5:8]}/{limpo[8:12]}-{limpo[12:]}"


class Parte(BaseModel):
    """
    Participante de um processo judicial — pessoa física ou jurídica.

    Campos obrigatórios conforme art. 9º Res. 403/2023:
    nome, documento (CPF ou CNPJ), endereço, e-mail e telefone.
    """
    nome: str = Field(min_length=2)
    tipo_pessoa: TipoPessoa
    cpf: str | None = None
    cnpj: str | None = None
    email: str = Field(min_length=5)
    telefone: str = Field(min_length=10)
    endereco: Endereco

    @field_validator("cpf")
    @classmethod
    def _validar_cpf(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validar_cpf(v)

    @field_validator("cnpj")
    @classmethod
    def _validar_cnpj(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validar_cnpj(v)

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("E-mail inválido")
        return v.lower().strip()

    @field_validator("telefone")
    @classmethod
    def _validar_telefone(cls, v: str) -> str:
        limpo = re.sub(r"[^0-9]", "", v)
        if len(limpo) < 10 or len(limpo) > 11:
            raise ValueError("Telefone deve conter 10 ou 11 dígitos")
        return limpo

    def model_post_init(self, __context: object) -> None:
        """Valida que pessoa física tem CPF e jurídica tem CNPJ."""
        if self.tipo_pessoa == TipoPessoa.FISICA and not self.cpf:
            raise ValueError("Pessoa física deve informar CPF")
        if self.tipo_pessoa == TipoPessoa.JURIDICA and not self.cnpj:
            raise ValueError("Pessoa jurídica deve informar CNPJ")


class Advogado(BaseModel):
    """Representante legal com inscrição na OAB."""
    nome: str = Field(min_length=2)
    oab_numero: str = Field(min_length=1)
    oab_uf: UF
    email: str = Field(min_length=5)
    telefone: str = Field(min_length=10)

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("E-mail inválido")
        return v.lower().strip()

    @field_validator("telefone")
    @classmethod
    def _validar_telefone(cls, v: str) -> str:
        limpo = re.sub(r"[^0-9]", "", v)
        if len(limpo) < 10 or len(limpo) > 11:
            raise ValueError("Telefone deve conter 10 ou 11 dígitos")
        return limpo
