"""
Modelos de partes do procedimento CEJUSC pré-processual.

Especializa os modelos base de juizo-core para o contexto da Res. 403/2023:
- ReclamanteCejusc: solicitante da reclamação (art. 9º)
- ReclamadoCejusc: parte solicitada
- AdvogadoCejusc: representante legal (opcional no pré-processual)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from juizo.models.partes import Advogado, Endereco, Parte, TipoPessoa, UF


class ReclamanteCejusc(BaseModel):
    """
    Reclamante (solicitante) do procedimento pré-processual CEJUSC.

    art. 9º — qualificação completa obrigatória:
    nome, CPF/CNPJ, endereço, e-mail, telefone.
    """
    parte: Parte
    advogado: Advogado | None = None  # representação facultativa


class ReclamadoCejusc(BaseModel):
    """
    Reclamado (solicitado) do procedimento pré-processual CEJUSC.

    art. 9º — qualificação completa obrigatória:
    nome, CPF/CNPJ, endereço, e-mail, telefone.
    """
    parte: Parte
    advogado: Advogado | None = None
