"""
FSM dos Juizados Especiais Civeis — Lei 9.099/95.

Estados, transicoes e regras de negocio extraidas diretamente da lei.
Cada regra tem referencia ao artigo correspondente.

Rito sumarissimo — procedimento simplificado para causas de menor
complexidade com valor ate 40 salarios minimos.
"""

from __future__ import annotations
from enum import Enum
from datetime import timedelta
from decimal import Decimal


class EstadoJEC(str, Enum):
    """
    Estados da maquina de estados do rito sumarissimo — Juizados Especiais Civeis.
    Lei 9.099/95
    """
    # -- Fase postulatoria --
    PETICAO_INICIAL                  = "PETICAO_INICIAL"                   # art. 14
    ANALISE_ADMISSIBILIDADE          = "ANALISE_ADMISSIBILIDADE"            # art. 16
    CITACAO_EXPEDIDA                 = "CITACAO_EXPEDIDA"                   # art. 18

    # -- Fase conciliatoria (obrigatoria — art. 21) --
    AUDIENCIA_CONCILIACAO_DESIGNADA  = "AUDIENCIA_CONCILIACAO_DESIGNADA"    # art. 21
    AUDIENCIA_CONCILIACAO_REALIZADA  = "AUDIENCIA_CONCILIACAO_REALIZADA"    # art. 21-22

    # -- Fase instrutoria --
    CONTESTACAO_RECEBIDA             = "CONTESTACAO_RECEBIDA"               # art. 30
    AUDIENCIA_INSTRUCAO_DESIGNADA    = "AUDIENCIA_INSTRUCAO_DESIGNADA"      # art. 27
    AUDIENCIA_INSTRUCAO_REALIZADA    = "AUDIENCIA_INSTRUCAO_REALIZADA"      # art. 28-29

    # -- Fase decisoria --
    CONCLUSO_SENTENCA                = "CONCLUSO_SENTENCA"                  # art. 38
    SENTENCA_PROFERIDA               = "SENTENCA_PROFERIDA"                 # art. 38-40

    # -- Recursos (Turma Recursal — art. 41-46) --
    RECURSO_INTERPOSTO               = "RECURSO_INTERPOSTO"                 # art. 41-43
    RECURSO_JULGADO                  = "RECURSO_JULGADO"                    # art. 46

    # -- Estados terminais (frozen — append-only encerra aqui) --
    ARQUIVADO_ACORDO_CONCILIACAO     = "ARQUIVADO_ACORDO_CONCILIACAO"       # art. 22
    ARQUIVADO_ACORDO_INSTRUCAO       = "ARQUIVADO_ACORDO_INSTRUCAO"         # acordo em AIJ
    ARQUIVADO_REVELIA                = "ARQUIVADO_REVELIA"                   # art. 20
    ARQUIVADO_DESISTENCIA            = "ARQUIVADO_DESISTENCIA"              # art. 51 I
    ARQUIVADO_EXTINCAO               = "ARQUIVADO_EXTINCAO"                 # art. 51
    TRANSITADO_EM_JULGADO            = "TRANSITADO_EM_JULGADO"              # tag v1.0.0


# -- Transicoes validas por estado --
# Qualquer tentativa de transicao fora deste dicionario
# levanta TransicaoInvalida — nulidades impossiveis por design.

TRANSICOES: dict[str, list[str]] = {
    EstadoJEC.PETICAO_INICIAL: [
        EstadoJEC.ANALISE_ADMISSIBILIDADE,
    ],
    EstadoJEC.ANALISE_ADMISSIBILIDADE: [
        EstadoJEC.CITACAO_EXPEDIDA,          # admitida — art. 16
        EstadoJEC.ARQUIVADO_EXTINCAO,        # art. 51 — inadmissivel (valor, competencia)
    ],
    EstadoJEC.CITACAO_EXPEDIDA: [
        EstadoJEC.AUDIENCIA_CONCILIACAO_DESIGNADA,  # citacao cumprida — art. 18
        EstadoJEC.ARQUIVADO_EXTINCAO,               # citacao frustrada — art. 51
    ],
    EstadoJEC.AUDIENCIA_CONCILIACAO_DESIGNADA: [
        EstadoJEC.AUDIENCIA_CONCILIACAO_REALIZADA,   # audiencia realizada
        EstadoJEC.ARQUIVADO_DESISTENCIA,             # art. 51 I — autor desiste
        EstadoJEC.ARQUIVADO_REVELIA,                 # art. 20 — reu ausente, efeitos da revelia
    ],
    EstadoJEC.AUDIENCIA_CONCILIACAO_REALIZADA: [
        EstadoJEC.ARQUIVADO_ACORDO_CONCILIACAO,  # art. 22 — acordo obtido
        EstadoJEC.CONTESTACAO_RECEBIDA,          # art. 30 — sem acordo, reu contesta
        EstadoJEC.ARQUIVADO_REVELIA,             # art. 20 — reu nao contesta
    ],
    EstadoJEC.CONTESTACAO_RECEBIDA: [
        EstadoJEC.AUDIENCIA_INSTRUCAO_DESIGNADA,  # art. 27 — necessita instrucao
        EstadoJEC.CONCLUSO_SENTENCA,              # julgamento antecipado — materia de direito
    ],
    EstadoJEC.AUDIENCIA_INSTRUCAO_DESIGNADA: [
        EstadoJEC.AUDIENCIA_INSTRUCAO_REALIZADA,  # audiencia realizada
        EstadoJEC.ARQUIVADO_DESISTENCIA,          # art. 51 I — desistencia
    ],
    EstadoJEC.AUDIENCIA_INSTRUCAO_REALIZADA: [
        EstadoJEC.CONCLUSO_SENTENCA,              # art. 28 — instrucao concluida
        EstadoJEC.ARQUIVADO_ACORDO_INSTRUCAO,     # acordo em audiencia de instrucao
    ],
    EstadoJEC.CONCLUSO_SENTENCA: [
        EstadoJEC.SENTENCA_PROFERIDA,             # art. 38
    ],
    EstadoJEC.SENTENCA_PROFERIDA: [
        EstadoJEC.RECURSO_INTERPOSTO,             # art. 41 — recurso inominado
        EstadoJEC.TRANSITADO_EM_JULGADO,          # nao recorreu — transito em julgado
    ],
    EstadoJEC.RECURSO_INTERPOSTO: [
        EstadoJEC.RECURSO_JULGADO,                # art. 46 — julgado pela Turma Recursal
    ],
    EstadoJEC.RECURSO_JULGADO: [
        EstadoJEC.TRANSITADO_EM_JULGADO,          # decisao definitiva
    ],
    # Terminais — sem saida
    EstadoJEC.ARQUIVADO_ACORDO_CONCILIACAO: [],
    EstadoJEC.ARQUIVADO_ACORDO_INSTRUCAO:  [],
    EstadoJEC.ARQUIVADO_REVELIA:           [],
    EstadoJEC.ARQUIVADO_DESISTENCIA:       [],
    EstadoJEC.ARQUIVADO_EXTINCAO:          [],
    EstadoJEC.TRANSITADO_EM_JULGADO:       [],
}

# -- Estados terminais --
ESTADOS_TERMINAIS: set[str] = {
    EstadoJEC.ARQUIVADO_ACORDO_CONCILIACAO,
    EstadoJEC.ARQUIVADO_ACORDO_INSTRUCAO,
    EstadoJEC.ARQUIVADO_REVELIA,
    EstadoJEC.ARQUIVADO_DESISTENCIA,
    EstadoJEC.ARQUIVADO_EXTINCAO,
    EstadoJEC.TRANSITADO_EM_JULGADO,
}

# -- Prazos legais (Lei 9.099/95) --
# art. 18 §1o — prazo de citacao
PRAZO_CITACAO = timedelta(days=15)

# art. 20 — audiencia de conciliacao em ate 15 dias da citacao
PRAZO_AUDIENCIA_CONCILIACAO = timedelta(days=15)

# art. 42 — prazo para recurso inominado
PRAZO_RECURSO = timedelta(days=10)

# art. 52 IV — prazo para cumprimento de sentenca
PRAZO_CUMPRIMENTO_SENTENCA = timedelta(days=15)

# art. 27 — audiencia de instrucao e julgamento
PRAZO_AUDIENCIA_INSTRUCAO = timedelta(days=15)

# -- Valor maximo da causa (art. 3o I) --
# art. 3o I — ate 40 salarios minimos
# Salario minimo 2025: R$ 1.518,00
SALARIO_MINIMO = Decimal("1518.00")
VALOR_MAXIMO_CAUSA = SALARIO_MINIMO * 40  # R$ 60.720,00

# art. 9o — advogado facultativo ate 20 SM, obrigatorio acima
LIMITE_SEM_ADVOGADO = SALARIO_MINIMO * 20  # R$ 30.360,00

# -- Permissoes por estado (quem pode provocar cada transicao) --
# Permissao e por estado_destino, nao por transicao.
PERMISSOES: dict[str, list[str]] = {
    EstadoJEC.ANALISE_ADMISSIBILIDADE:         ["SECRETARIA"],
    EstadoJEC.CITACAO_EXPEDIDA:                ["SECRETARIA"],
    EstadoJEC.AUDIENCIA_CONCILIACAO_DESIGNADA: ["SECRETARIA"],
    EstadoJEC.AUDIENCIA_CONCILIACAO_REALIZADA: ["CONCILIADOR"],
    EstadoJEC.CONTESTACAO_RECEBIDA:            ["SECRETARIA"],
    EstadoJEC.AUDIENCIA_INSTRUCAO_DESIGNADA:   ["SECRETARIA", "JUIZ"],
    EstadoJEC.AUDIENCIA_INSTRUCAO_REALIZADA:   ["JUIZ"],
    EstadoJEC.CONCLUSO_SENTENCA:               ["SECRETARIA", "JUIZ"],
    EstadoJEC.SENTENCA_PROFERIDA:              ["JUIZ"],
    EstadoJEC.RECURSO_INTERPOSTO:              ["PARTE", "ADVOGADO"],
    EstadoJEC.RECURSO_JULGADO:                 ["TURMA_RECURSAL"],
    EstadoJEC.ARQUIVADO_ACORDO_CONCILIACAO:    ["CONCILIADOR", "SECRETARIA"],
    EstadoJEC.ARQUIVADO_ACORDO_INSTRUCAO:      ["JUIZ", "SECRETARIA"],
    EstadoJEC.ARQUIVADO_REVELIA:               ["JUIZ", "SECRETARIA"],
    EstadoJEC.ARQUIVADO_DESISTENCIA:           ["PARTE", "ADVOGADO", "SECRETARIA"],
    EstadoJEC.ARQUIVADO_EXTINCAO:              ["JUIZ", "SECRETARIA"],
    EstadoJEC.TRANSITADO_EM_JULGADO:           ["SECRETARIA"],
}

# -- Materias excluidas da competencia dos Juizados Especiais (art. 3o §2o) --
MATERIAS_EXCLUIDAS: list[dict] = [
    {"codigo": "NATUREZA_ALIMENTAR",
     "descricao": "Causas de natureza alimentar",
     "artigo": "art. 3o §2o Lei 9.099/95"},
    {"codigo": "NATUREZA_FALIMENTAR",
     "descricao": "Causas de natureza falimentar",
     "artigo": "art. 3o §2o Lei 9.099/95"},
    {"codigo": "NATUREZA_FISCAL",
     "descricao": "Causas de natureza fiscal",
     "artigo": "art. 3o §2o Lei 9.099/95"},
    {"codigo": "INTERESSE_FAZENDA_PUBLICA",
     "descricao": "Causas de interesse da Fazenda Publica",
     "artigo": "art. 3o §2o Lei 9.099/95"},
    {"codigo": "ACIDENTE_TRABALHO",
     "descricao": "Causas relativas a acidentes de trabalho",
     "artigo": "art. 3o §2o Lei 9.099/95"},
    {"codigo": "RESIDUO_ESTADO",
     "descricao": "Causas relativas a residuos e ao estado e capacidade das pessoas",
     "artigo": "art. 3o §2o Lei 9.099/95"},
]
