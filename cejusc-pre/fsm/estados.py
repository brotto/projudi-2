"""
FSM do CEJUSC pré-processual — Res. 403/2023 NUPEMEC TJPR.

Estados, transições e regras de negócio extraídas diretamente da resolução.
Cada regra tem referência ao artigo correspondente.
"""

from __future__ import annotations
from enum import Enum
from datetime import timedelta


class EstadoCejusc(str, Enum):
    """
    Estados da máquina de estados do procedimento pré-processual CEJUSC.
    Res. 403/2023 · NUPEMEC · TJPR
    """
    # ── Fluxo principal ──
    SOLICITACAO_RECEBIDA   = "SOLICITACAO_RECEBIDA"    # art. 7º
    TRIAGEM                = "TRIAGEM"                  # art. 7º §2º
    VERIFICACAO_CUSTAS     = "VERIFICACAO_CUSTAS"       # art. 8º
    ANALISE_GRATUIDADE     = "ANALISE_GRATUIDADE"       # art. 8º §3º
    CADASTRADO             = "CADASTRADO"               # art. 7º §3º
    SESSAO_AGENDADA        = "SESSAO_AGENDADA"          # art. 10º II
    NOTIFICACOES_ENVIADAS  = "NOTIFICACOES_ENVIADAS"    # art. 10º III/IV
    SESSAO_CONDUZIDA       = "SESSAO_CONDUZIDA"         # art. 11–12
    SESSAO_CONTINUADA      = "SESSAO_CONTINUADA"        # art. 12 §4º / art. 14
    ACORDO_REDIGIDO        = "ACORDO_REDIGIDO"          # art. 13 §3º
    AGUARDANDO_MP          = "AGUARDANDO_MP"            # art. 15 §ú
    CONCLUSO_JUIZ          = "CONCLUSO_JUIZ"            # art. 15
    HOMOLOGADO             = "HOMOLOGADO"               # art. 15

    # ── Estados terminais (frozen — append-only encerra aqui) ──
    ARQUIVADO_ACORDO       = "ARQUIVADO_ACORDO"         # art. 16 · título executivo
    ARQUIVADO_SEM_ACORDO   = "ARQUIVADO_SEM_ACORDO"     # art. 4º · sem prevenção
    ARQUIVADO_AUSENCIA     = "ARQUIVADO_AUSENCIA"       # art. 12 §3º · imediato
    ARQUIVADO_FALTA_CUSTAS = "ARQUIVADO_FALTA_CUSTAS"   # art. 8º §4º · imediato
    ARQUIVADO_INCOMPETENTE = "ARQUIVADO_INCOMPETENTE"   # art. 6º §1º
    ARQUIVADO_IRREGULAR    = "ARQUIVADO_IRREGULAR"      # art. 9º §2º · 5 dias


# ── Transições válidas por estado ──
# Qualquer tentativa de transição fora deste dicionário
# levanta TransicaoInvalida — nulidades impossíveis por design.

TRANSICOES: dict[str, list[str]] = {
    EstadoCejusc.SOLICITACAO_RECEBIDA: [
        EstadoCejusc.TRIAGEM,
    ],
    EstadoCejusc.TRIAGEM: [
        EstadoCejusc.VERIFICACAO_CUSTAS,     # adequada + competente
        EstadoCejusc.ARQUIVADO_INCOMPETENTE, # art. 6º §1º — matéria excluída
        EstadoCejusc.ARQUIVADO_IRREGULAR,    # art. 9º §2º — não regularizou em 5 dias
    ],
    EstadoCejusc.VERIFICACAO_CUSTAS: [
        EstadoCejusc.CADASTRADO,             # taxa paga
        EstadoCejusc.ANALISE_GRATUIDADE,     # art. 8º §3º — pedido de gratuidade
        EstadoCejusc.ARQUIVADO_FALTA_CUSTAS, # art. 8º §4º — não recolheu
    ],
    EstadoCejusc.ANALISE_GRATUIDADE: [
        EstadoCejusc.CADASTRADO,             # gratuidade deferida
        EstadoCejusc.ARQUIVADO_FALTA_CUSTAS, # indeferida + não pagou
    ],
    EstadoCejusc.CADASTRADO: [
        EstadoCejusc.SESSAO_AGENDADA,
    ],
    EstadoCejusc.SESSAO_AGENDADA: [
        EstadoCejusc.NOTIFICACOES_ENVIADAS,
    ],
    EstadoCejusc.NOTIFICACOES_ENVIADAS: [
        EstadoCejusc.SESSAO_CONDUZIDA,       # ambas presentes
        EstadoCejusc.ARQUIVADO_AUSENCIA,     # art. 12 §3º — ausência
    ],
    EstadoCejusc.SESSAO_CONDUZIDA: [
        EstadoCejusc.SESSAO_CONTINUADA,      # art. 12 §4º — necessita continuação
        EstadoCejusc.ACORDO_REDIGIDO,        # acordo obtido
        EstadoCejusc.ARQUIVADO_SEM_ACORDO,   # art. 12 §3º — infrutífera
        EstadoCejusc.ARQUIVADO_AUSENCIA,     # art. 12 §3º — ausência durante
    ],
    EstadoCejusc.SESSAO_CONTINUADA: [
        EstadoCejusc.SESSAO_CONTINUADA,      # nova continuação (max 60 dias)
        EstadoCejusc.ACORDO_REDIGIDO,
        EstadoCejusc.ARQUIVADO_SEM_ACORDO,
        EstadoCejusc.ARQUIVADO_AUSENCIA,
    ],
    EstadoCejusc.ACORDO_REDIGIDO: [
        EstadoCejusc.AGUARDANDO_MP,          # art. 6º — menores/incapazes
        EstadoCejusc.CONCLUSO_JUIZ,          # caso direto
    ],
    EstadoCejusc.AGUARDANDO_MP: [
        EstadoCejusc.CONCLUSO_JUIZ,          # após manifestação do MP
    ],
    EstadoCejusc.CONCLUSO_JUIZ: [
        EstadoCejusc.HOMOLOGADO,
    ],
    EstadoCejusc.HOMOLOGADO: [
        EstadoCejusc.ARQUIVADO_ACORDO,
    ],
    # Terminais — sem saída
    EstadoCejusc.ARQUIVADO_ACORDO:       [],
    EstadoCejusc.ARQUIVADO_SEM_ACORDO:   [],
    EstadoCejusc.ARQUIVADO_AUSENCIA:     [],
    EstadoCejusc.ARQUIVADO_FALTA_CUSTAS: [],
    EstadoCejusc.ARQUIVADO_INCOMPETENTE: [],
    EstadoCejusc.ARQUIVADO_IRREGULAR:    [],
}

# ── Estados terminais ──
ESTADOS_TERMINAIS: set[str] = {
    EstadoCejusc.ARQUIVADO_ACORDO,
    EstadoCejusc.ARQUIVADO_SEM_ACORDO,
    EstadoCejusc.ARQUIVADO_AUSENCIA,
    EstadoCejusc.ARQUIVADO_FALTA_CUSTAS,
    EstadoCejusc.ARQUIVADO_INCOMPETENTE,
    EstadoCejusc.ARQUIVADO_IRREGULAR,
}

# ── Prazos legais (art. 14 · Res. 403/2023) ──
PRAZO_REGULARIZACAO      = timedelta(days=5)   # art. 9º §2º
PRAZO_MAX_SEM_SESSAO     = timedelta(days=30)  # art. 14
PRAZO_MAX_CONTINUADA     = timedelta(days=60)  # art. 14

# ── Permissões por estado (quem pode provocar cada transição) ──
PERMISSOES: dict[str, list[str]] = {
    EstadoCejusc.TRIAGEM:               ["SECRETARIA"],
    EstadoCejusc.VERIFICACAO_CUSTAS:    ["SECRETARIA"],
    EstadoCejusc.ANALISE_GRATUIDADE:    ["SECRETARIA", "JUIZ_COORDENADOR"],
    EstadoCejusc.CADASTRADO:            ["SECRETARIA", "JUIZ_COORDENADOR"],
    EstadoCejusc.SESSAO_AGENDADA:       ["SECRETARIA"],
    EstadoCejusc.NOTIFICACOES_ENVIADAS: ["SECRETARIA"],
    EstadoCejusc.SESSAO_CONDUZIDA:      ["CONCILIADOR", "MEDIADOR"],
    EstadoCejusc.SESSAO_CONTINUADA:     ["CONCILIADOR", "MEDIADOR"],
    EstadoCejusc.ACORDO_REDIGIDO:       ["CONCILIADOR", "MEDIADOR"],
    EstadoCejusc.AGUARDANDO_MP:         ["SECRETARIA"],
    EstadoCejusc.CONCLUSO_JUIZ:         ["SECRETARIA"],
    EstadoCejusc.HOMOLOGADO:            ["JUIZ_COORDENADOR"],
    EstadoCejusc.ARQUIVADO_ACORDO:      ["SECRETARIA"],
    EstadoCejusc.ARQUIVADO_SEM_ACORDO:  ["CONCILIADOR", "MEDIADOR", "SECRETARIA"],
    EstadoCejusc.ARQUIVADO_AUSENCIA:    ["CONCILIADOR", "MEDIADOR", "SECRETARIA"],
    EstadoCejusc.ARQUIVADO_FALTA_CUSTAS:["SECRETARIA", "JUIZ_COORDENADOR"],
    EstadoCejusc.ARQUIVADO_INCOMPETENTE:["SECRETARIA"],
    EstadoCejusc.ARQUIVADO_IRREGULAR:   ["SECRETARIA"],
}

# ── Matérias excluídas da competência (art. 6º §1º) ──
MATERIAS_EXCLUIDAS: list[dict] = [
    {"codigo": "DIREITO_INDISPONIVEL_NAO_TRANSACIONAVEL",
     "descricao": "Direitos indisponíveis não transacionáveis",
     "artigo": "art. 6º §1º I · art. 3º Lei 13.140/2015"},
    {"codigo": "COMPETENCIA_FEDERAL",
     "descricao": "Matérias de competência federal (mesmo que delegadas)",
     "artigo": "art. 6º §1º II"},
    {"codigo": "CRIMINAL",
     "descricao": "Matérias de natureza criminal",
     "artigo": "art. 6º §1º III"},
    {"codigo": "TRABALHISTA",
     "descricao": "Matérias de natureza trabalhista",
     "artigo": "art. 6º §1º III"},
    {"codigo": "SUCESSORIO",
     "descricao": "Matéria sucessória (inventários, arrolamentos, partilhas, alvarás)",
     "artigo": "art. 6º §1º IV"},
    {"codigo": "REGIME_BENS",
     "descricao": "Alteração de regime de bens de casamento",
     "artigo": "art. 6º §1º V"},
    {"codigo": "USUCAPIAO_IMOVEL",
     "descricao": "Usucapião de bens imóveis",
     "artigo": "art. 6º §1º VI"},
    {"codigo": "PRODUCAO_PROBATORIA",
     "descricao": "Questões que envolvam produção probatória",
     "artigo": "art. 6º §1º VII"},
]
