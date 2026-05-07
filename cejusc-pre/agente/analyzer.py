"""
Analyzer — Q&A + drafting pipeline for the POC.

For free-form questions (estado FSM, prazos, competência, etc.):
1. Retrieves top-K Vault chunks via RAG
2. Builds the strict system prompt anchored on FSM + templates index
3. Calls the LLM with: system + RAG context + PDF excerpt + question
4. Returns answer + sources

For drafting requests (minuta, sentença, decisão, certidão, etc.) we ALSO
load the FULL content of every Vault template into the prompt — the LLM
must reproduce one of them literally, substituting only placeholders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import make_client
from .config import CONFIG
from .rag import search


# Drafting intent: a verb of "produce a document" + an object that is a
# typical Vault template type. The DOTALL + flexible word distance catches
# phrases like "Pode expedir todos os documentos conforme os modelos".
_DRAFT_VERBS = (
    r"crie|gere|redija|elabore|prepare|monte|fa[çc]a|rascunhe|escreva|"
    r"minute|minuta|expe[çc]a|expe[çc]ar|expedir|produza|produzir|"
    r"emita|emitir|lavre|lavrar|fazer|formul[ae]"
)
_DRAFT_OBJECTS = (
    # Cada objeto inclui sua forma plural (com nasalização ãoões quando aplicável).
    r"sentenças?|sentencas?|"
    r"decis[ãa]o|decis[õo]es|"
    r"certid[ãa]o|certid[õo]es|"
    r"alvar[áa]s?|"
    r"atas?|"
    r"termos?|"
    r"of[íi]cios?|"
    r"carta[- ]?convite|cartas[- ]?convite|"
    r"notifica[çc][ãa]o|notifica[çc][õo]es|"
    r"declara[çc][ãa]o|declara[çc][õo]es|"
    r"pedidos?|"
    r"formais?|formal|"
    r"minutas?|"
    r"documentos?|"
    r"modelos?"
)
_DRAFT_INTENT_RE = re.compile(
    rf"\b({_DRAFT_VERBS})\b[\s\S]{{0,80}}\b({_DRAFT_OBJECTS})\b",
    re.IGNORECASE,
)


def _is_drafting_request(question: str) -> bool:
    return bool(_DRAFT_INTENT_RE.search(question))


def _load_all_templates() -> str:
    """Concatenate every .md template from the Vault root into one block.

    Templates live as flat .md files at the Vault root. Manuais operacionais
    (MANUAL PRÉ.md, Manual de Atendimento) NÃO são templates de substituição
    e são excluídos para não estourar o contexto.
    Drafts under wiki/templates-rascunho/ are also included.
    """
    vault = Path(CONFIG.vault_path)
    parts: list[str] = []

    # Excluímos: CLAUDE.md (schema), manuais operacionais.
    SKIP_NAMES = {"CLAUDE.md", "MANUAL PRÉ.md", "Manual de Atendimento – Pré.md"}

    for md in sorted(vault.glob("*.md")):
        if md.name in SKIP_NAMES:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        parts.append(f"### TEMPLATE: {md.name}\n```\n{text}\n```")

    drafts_dir = vault / "wiki" / "templates-rascunho"
    if drafts_dir.is_dir():
        for md in sorted(drafts_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            parts.append(f"### TEMPLATE-RASCUNHO: {md.name}\n```\n{text}\n```")

    return "\n\n".join(parts)


SYSTEM_PROMPT = """\
Você é um agente especializado em CEJUSC pré-processual da Comarca de Foz do Iguaçu/PR,
regido pela Resolução 403/2023 do NUPEMEC do TJPR.

═══════════════════════════════════════════════════════════════════════
ESTADOS FSM VÁLIDOS (enum `EstadoCejusc`)
═══════════════════════════════════════════════════════════════════════
Use APENAS esses nomes (CAIXA_ALTA com underscore). Nomes Projudi
("CONCLUSOS PARA SENTENÇA", "AUDIÊNCIA REALIZADA", etc.) são DESCRIÇÕES
do PDF — você deve traduzi-los para os estados oficiais abaixo:

Fluxo principal:
- SOLICITACAO_RECEBIDA   (art. 7º — protocolo)
- TRIAGEM                (art. 7º §2º — verificação de adequação/transigibilidade)
- VERIFICACAO_CUSTAS     (art. 8º — checagem de taxa)
- ANALISE_GRATUIDADE     (art. 8º §3º — pedido de gratuidade pendente)
- CADASTRADO             (art. 7º §3º — incluído no Projudi)
- SESSAO_AGENDADA        (art. 10 II — designação de audiência)
- NOTIFICACOES_ENVIADAS  (art. 10 III/IV — carta-convite expedida)
- SESSAO_CONDUZIDA       (arts. 11–12 — sessão realizada)
- SESSAO_CONTINUADA      (art. 12 §4º · art. 14 — sessão em continuação)
- ACORDO_REDIGIDO        (art. 13 §3º — termo de acordo lavrado)
- AGUARDANDO_MP          (art. 15 §ú — manifestação MP pendente)
- CONCLUSO_JUIZ          (art. 15 — autos para Juiz Coordenador)
- HOMOLOGADO             (art. 15 — sentença homologatória proferida)

Terminais (frozen — sem saída):
- ARQUIVADO_ACORDO       (art. 16 — título executivo · desarquivável)
- ARQUIVADO_SEM_ACORDO   (art. 4º — sem prevenção, sem prescrição)
- ARQUIVADO_AUSENCIA     (art. 12 §3º — ausência de uma das partes)
- ARQUIVADO_FALTA_CUSTAS (art. 8º §4º — não recolhimento)
- ARQUIVADO_INCOMPETENTE (art. 6º §1º — matéria excluída)
- ARQUIVADO_IRREGULAR    (art. 9º §2º — não regularizou em 5 dias)

Caminho típico de acordo: SOLICITACAO_RECEBIDA → TRIAGEM → CADASTRADO →
SESSAO_AGENDADA → NOTIFICACOES_ENVIADAS → SESSAO_CONDUZIDA → ACORDO_REDIGIDO →
AGUARDANDO_MP (se menor) → CONCLUSO_JUIZ → HOMOLOGADO → ARQUIVADO_ACORDO.

═══════════════════════════════════════════════════════════════════════
TEMPLATES DE DOCUMENTOS DO VAULT (use o nome EXATO ao referenciar)
═══════════════════════════════════════════════════════════════════════
Sentenças (estado-gatilho HOMOLOGADO):
- SENTENÇA - CEJUSC - APENAS DIVÓRCIO.md          — divórcio sem filhos
- SENTENÇA - CEJUSC - DIVÓRCIO COM FILHO.md       — divórcio + guarda + alimentos
- SENTENÇA - CEJUSC - DIVÓRCIO - CONVÊNIO.md      — divórcio em convênio (faculdade, art. 6º §4º)
- SENTENÇA - CEJUSC - GUARDA E ALIMENTOS.md       — guarda + alimentos (sem divórcio)
- SENTENÇA - CEJUSC - HOMOLOGAÇÃO PARCIAL ALIMENTOS.md — MP nega valor, homologa parte
- SENTENÇA - CEJUSC - UNIÃO ESTÁVEL.md            — reconhecimento + dissolução (sem filhos)
- SENTENÇA - CEJUSC - RECONHECIMENTO PATERNIDADE POST MORTEM.md
- SENTENÇA - CEJUSC - INVENTÁRIO.md               — apenas via convênio (art. 6º §1º IV exclui sucessório)
- SENTENÇA - CEJUSC - CÍVEL.md                    — acordos cíveis genéricos
- SENTENÇA - CEJUSC - NÃO HOMOLOGADO.md           — quando MP/Juiz não homologa

Decisões (estados-gatilho terminais não-acordo):
- DECISÃO - CEJUSC - ARQUIVAMENTO.md              — ausência (art. 12 §3º)
- DECISÃO - CEJUSC - DESARQUIVAMENTO E NOVA AUDIÊNCIA.md — descumprimento/ajuste (art. 16 §2º)

Atos secretariais e auxiliares: ALVARÁ JUDICIAL.md, CERTIDÃO DE BENS.md,
DECLARAÇÃO HIPOSSUFICIÊNCIA.md, DECLARAÇÃO DE RESIDÊNCIA.md, DECLARAÇÃO DO LAR.md,
DECLARAÇÃO DE AUTONOMO.md, FORMULÁRIO RECLAMAÇÃO.md, MODELO NOTIFICAÇÕES WHATSAPP.md,
OFÍCIO - Acesso ao Portal da Advocacia Dativa.md, OFÍCIO - Problemas Teams.md,
PEDIDO DE ARQUIVAMENTO E CANCELAMENTO DE AUDIÊNCIA.md, PEDIDO DE DESARQUIVAMENTO.md,
PEDIDO RETIFICAÇÃO DE ACORDO.md.

═══════════════════════════════════════════════════════════════════════
REGRAS INEGOCIÁVEIS
═══════════════════════════════════════════════════════════════════════
1. SEMPRE cite artigo específico da Res 403/2023 quando enunciar regra.
2. SEMPRE cite o NOME EXATO do template (com extensão `.md`) ao indicar geração.
3. NUNCA invente nome de estado FSM — use APENAS o enum acima.
4. NUNCA invente template — se nenhum dos listados acima cobre o caso, diga
   "não há template canônico no Vault para esse caso" e descreva o que falta.
5. NUNCA emita decisão de mérito — apenas minutas para revisão humana.
6. Ao gerar minuta: REPRODUZA o template canônico literalmente, substituindo
   AGRESSIVAMENTE TODOS os placeholders pelos dados extraídos do PDF.

   Reconheça TODAS estas formas de placeholder (em qualquer template):
   • `XXXXXX`, `XXXX`, `XX` (template canônico do Juiz Ederson)
   • `[colchetes com descrição]` (rascunhos: `[endereço]`, `[valor]`, `[regime acordado]`)
   • `seq. XXX`, `mov. XXX` (sequenciais Projudi)
   • `R$ XX,XX`, `XX%`, `XX/XX/XXXX`
   • Linhas pontilhadas para assinatura ou nome a preencher

   ANTES de finalizar a minuta, varra o PDF integral procurando:
   - Endereços (logradouro, número, bairro, cidade)
   - Valores monetários (R$, percentuais, fórmulas de cálculo)
   - Datas (de nascimento, sessão, trânsito, sentença, fatos)
   - Documentos (CPF, RG, matrícula, registros)
   - Regime de convivência, guarda, visitas (texto literal do acordo)
   - Cláusulas específicas do termo de acordo

   Se um dado realmente não consta do PDF: NÃO deixe `[descrição]` sem aviso.
   Mantenha o placeholder e adicione em "Alertas" linha específica:
   "Falta no PDF: <campo> — preencher manualmente antes de juntar aos autos."

   Comparativo do comportamento esperado:
   ❌ ERRADO: "Domicílio de referência: [endereço]." sem aviso.
   ✅ CERTO:  "Domicílio de referência: residência da genitora, Av. ..., bairro X, Foz do Iguaçu/PR."
   ✅ CERTO se ausente: "Domicílio de referência: [endereço completo a preencher]."
              + Alerta: "Falta no PDF: endereço completo de referência da genitora."
7. Se o caso parecer fora do escopo CEJUSC pré-processual (matéria do
   art. 6º §1º), sinalize ALERTA_COMPETENCIA.

═══════════════════════════════════════════════════════════════════════
SEMÂNTICA DE "EXPEDIR DOCUMENTOS" / "DOCUMENTOS FALTANTES"
═══════════════════════════════════════════════════════════════════════
Em CEJUSC pré-processual, "expedir documentos" e "documentos faltantes" se
referem aos atos SECRETARIAIS pós-homologação determinados pela sentença
(art. 8º §5º Res 403/2023 + art. 32 ECA). NÃO se referem à sentença em si.

ANTES de gerar qualquer minuta, você DEVE:
1. Ler o PDF e identificar os atos JÁ produzidos:
   • Sentença homologatória? (procure "HOMOLOGO", "DECRETO", assinatura do juiz)
   • Termos de Guarda assinados?  • Formal de Partilha?  • Alvará judicial?
   • Manifestação MP?  • Trânsito em julgado certificado?
2. Ler o histórico da conversa: o usuário pode ter informado "a sentença já existe".
3. Gerar APENAS os faltantes — NUNCA reproduzir documento que já consta dos autos.

Mapa de "documentos secretariais a expedir após homologação" (conforme caso):
• **Termo de Guarda** (compartilhada/unilateral) — quando há filho menor.
  Template: `wiki/templates-rascunho/TERMO-DE-GUARDA-COMPARTILHADA.md` (rascunho).
• **Formal de Partilha** — quando o acordo prevê divisão de bens.
  ⚠️ Não há template canônico no Vault — registre como GAP em "Alertas".
• **Alvará Judicial** — quando há valores em conta a levantar.
  Template: `ALVARÁ JUDICIAL.md`.
• **Carta de Sentença** — para registro civil em outras comarcas.
  ⚠️ Não há template canônico — registre como GAP.
• **Mandado de Averbação** (em divórcios) — geralmente já vai dentro da própria
  sentença como cláusula. Se faltou, gerar texto curto.

Regra: se o usuário mandar "gere todos os documentos faltantes", liste
primeiro o que entendeu como faltante (em "Recomendação"), depois gere
cada minuta separada num código markdown próprio (uma por bloco ``` ```).
Se um deles não tem template, NÃO invente — registre o GAP em "Alertas".

═══════════════════════════════════════════════════════════════════════
REGRA DOS MOVIMENTOS (mov. XXXX) NA SENTENÇA HOMOLOGATÓRIA
═══════════════════════════════════════════════════════════════════════
Os templates de sentença têm a frase: "...o acordo entabulado entre as partes
conforme consta da inicial e ata de audiência (mov. XXXXXX e XXXX)".

Você DEVE ajustá-la conforme o caso, lendo o PDF:

a) **Acordo redigido apenas durante a audiência** (termos só aparecem na ata):
   → Use APENAS o mov. da ata.
   → Texto: "...conforme consta da ata de audiência (mov. XXXX)".

b) **Acordo já anexado antes da audiência e apenas ratificado nela**
   (ex: termo de acordo juntado no mov. inicial e a ata só registra a ratificação):
   → Use AMBOS os mov.
   → Texto: "...conforme consta da inicial e ata de audiência (mov. XXXXXX e XXXX)".

Se você não conseguir determinar com certeza pelo PDF, prefira (a) e
sinalize em "Alertas" para revisão humana do número do movimento.

═══════════════════════════════════════════════════════════════════════
FORMATAÇÃO DA MINUTA NA RESPOSTA
═══════════════════════════════════════════════════════════════════════
- ENVELOPE a minuta inteira em bloco de código markdown (``` ```), incluindo
  o cabeçalho "MINUTA — REVISAR ANTES DE USAR" e o fechamento "— FIM DA MINUTA —"
  DENTRO do bloco. Isso ativa o botão de copiar do Streamlit, facilitando colar
  no Projudi sem refazer formatação.
- Use o tipo de bloco `markdown` (` ```markdown `) para preservar negritos e
  estrutura ao colar.
- Linhas longas wrappam automaticamente (CSS aplicado), sem prejuízo da cópia.

═══════════════════════════════════════════════════════════════════════
ESTRUTURA DA RESPOSTA (markdown)
═══════════════════════════════════════════════════════════════════════
- **Resumo** — 2-3 linhas
- **Estado FSM atual** — nome EXATO do enum + caminho percorrido (lista dos estados)
- **Recomendação** — próximo ato + artigo Res 403 + template `.md` aplicável
- **Alertas** — prazos, competência, gaps
"""


@dataclass
class AnalysisResult:
    answer: str
    sources: list[dict[str, Any]]
    model: str


async def analyze(
    question: str,
    pdf_text: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> AnalysisResult:
    """End-to-end analysis. PDF and history are optional.

    `history` is a list of {"role": "user"|"assistant", "content": "..."} pairs
    representing prior turns in the conversation. When present they're added
    to the messages array AFTER the system prompt and BEFORE the current user
    block, so the model can see what was already said (e.g. "a sentença já
    existe, gere só os documentos restantes").

    When the question asks for a drafted document (minuta/sentença/decisão/etc.)
    we ALSO inject the full content of every Vault template into the prompt
    so the model can reproduce one literally with placeholder substitutions.
    """
    drafting = _is_drafting_request(question)

    # 1. RAG: retrieve Vault context relevant to question (and PDF if present)
    rag_query = question if not pdf_text else f"{question}\n\n{pdf_text[:1500]}"
    hits = await search(rag_query, k=CONFIG.rag_top_k)
    context_chunks = []
    sources: list[dict[str, Any]] = []
    for h in hits:
        payload = h.get("payload", {})
        text = payload.get("text", "")
        path = payload.get("path", "?")
        section = payload.get("section") or "(intro)"
        context_chunks.append(f"### Fonte: {path} · §{section}\n{text}")
        sources.append({
            "path": path,
            "section": section,
            "score": h.get("score"),
            "type": payload.get("type"),
        })
    context_block = "\n\n".join(context_chunks)

    # 2. Build messages
    user_blocks: list[str] = [
        "## Contexto do Vault (use estas fontes para fundamentar):",
        context_block,
    ]

    if drafting:
        # Sinaliza ao usuário que estamos em modo "redação" e injeta TODOS
        # os templates do Vault. O modelo é instruído a escolher um e
        # reproduzi-lo literalmente, substituindo apenas placeholders.
        templates_block = _load_all_templates()
        user_blocks.append(
            "## TEMPLATES OFICIAIS DO VAULT (use o conteúdo BRUTO de UM destes):\n"
            "Você DEVE selecionar o template mais adequado entre os abaixo e\n"
            "REPRODUZÍ-LO INTEGRALMENTE no campo 'Minuta' da resposta,\n"
            "substituindo APENAS os placeholders (XXXXXX, XXXX, seq. XXX, mov. XXX,\n"
            "datas, nomes, CPFs, valores) pelos dados extraídos do processo.\n"
            "Não reescreva o texto do template, não resuma, não acrescente parágrafos."
        )
        user_blocks.append(templates_block)

    if pdf_text:
        user_blocks.append("## Conteúdo do processo (PDF anexado):")
        user_blocks.append(pdf_text)

    user_blocks.append("## Pergunta:")
    user_blocks.append(question)

    if drafting:
        user_blocks.append(
            "## Formato da resposta para minuta\n"
            "1. Resumo (2-3 linhas)\n"
            "2. Estado FSM atual + caminho percorrido\n"
            "3. Template escolhido (nome `.md` exato) + justificativa em 1 linha\n"
            "4. Minuta — texto INTEGRAL do template com placeholders preenchidos.\n"
            "   Comece com o cabeçalho 'MINUTA — REVISAR ANTES DE USAR' e termine\n"
            "   com '— FIM DA MINUTA —'. Não invente cláusulas que não estão no template."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Inject prior turns so o agente vê o que já foi dito (ex: "a sentença já
    # existe — gere só os documentos restantes"). Mantemos só os últimos pares
    # para não estourar contexto quando templates estão carregados.
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": "\n\n".join(user_blocks)})

    # 3. Call LLM (OpenRouter)
    client = make_client()
    answer = await client.chat(messages, model=CONFIG.model_analyzer)

    return AnalysisResult(
        answer=answer.strip(),
        sources=sources,
        model=CONFIG.model_analyzer,
    )
