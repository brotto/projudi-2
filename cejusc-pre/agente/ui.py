"""
Streamlit UI — minimum viable interface to test the agent locally.

Run from cejusc-pre/:
    streamlit run agente/ui.py

Opens in your browser. Drop a PDF, type your question, see the answer.
No deploy, no integration — just a smoke-test surface for the analyzer.
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from pathlib import Path

# Streamlit runs this file as a script, not as a package member, so relative
# imports fail. Add cejusc-pre/ (parent of agente/) to sys.path so 'agente'
# resolves as a real package and its internal relative imports keep working.
_pkg_parent = str(Path(__file__).resolve().parent.parent)
if _pkg_parent not in sys.path:
    sys.path.insert(0, _pkg_parent)

import streamlit as st

from agente.analyzer import analyze
from agente.pdf import extract_text


st.set_page_config(
    page_title="Agente CEJUSC Pré · Análise",
    page_icon="⚖️",
    layout="wide",
)

# Força quebra de linha em qualquer bloco — mesmo se o modelo envelopar a
# minuta em ``` (code fence), o texto continua legível sem scroll horizontal.
st.markdown(
    """
    <style>
    pre, code {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: anywhere !important;
    }
    [data-testid="stChatMessageContent"] {
        max-width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ Agente CEJUSC Pré-Processual")
st.caption(
    "POC · Res. 403/2023 NUPEMEC TJPR · Comarca de Foz do Iguaçu/PR · "
    "self-hosted Qwen 14B + RAG sobre o Vault"
)

# ─── Session state ───────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []  # list of {"q", "a", "sources", "elapsed"}
if "uploader_key" not in st.session_state:
    # The file_uploader widget retains its file internally; rotating the key
    # is the canonical Streamlit way to truly reset it (i.e. "remove file").
    st.session_state.uploader_key = 0

# ─── Sidebar: upload + clear ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Processo")
    uploaded = st.file_uploader(
        "Anexe o PDF do processo (opcional)",
        type=["pdf"],
        help="O agente lê o conteúdo e usa junto com o conhecimento do Vault.",
        key=f"pdf_uploader_{st.session_state.uploader_key}",
    )
    if uploaded is not None:
        if "pdf_name" not in st.session_state or st.session_state.pdf_name != uploaded.name:
            with st.spinner("Lendo PDF..."):
                st.session_state.pdf_text = extract_text(io.BytesIO(uploaded.read()))
                st.session_state.pdf_name = uploaded.name
        st.success(
            f"📎 {st.session_state.pdf_name} ({len(st.session_state.pdf_text):,} caracteres)"
        )
        if st.button("Remover PDF", key="remove_pdf"):
            # Limpa o estado do PDF e força o file_uploader a renascer vazio.
            # Histórico da conversa é PRESERVADO — usar "Limpar conversa" para isso.
            st.session_state.pop("pdf_text", None)
            st.session_state.pop("pdf_name", None)
            st.session_state.uploader_key += 1
            st.rerun()
    else:
        # Saneamento defensivo: se o uploader voltou vazio por outra razão,
        # garante que o estado do PDF não fique órfão.
        st.session_state.pop("pdf_text", None)
        st.session_state.pop("pdf_name", None)

    st.divider()
    if st.button("Limpar conversa", key="clear_chat"):
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.caption(
        "**Modelo:** gpt-4o (OpenRouter)  \n"
        "**Embeddings:** nomic-embed-text (Ollama)  \n"
        "**Vetor:** Qdrant `cejusc-pre` (768d)"
    )

# ─── History ─────────────────────────────────────────────────────────────────
for turn in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(turn["q"])
    with st.chat_message("assistant"):
        st.markdown(turn["a"])
        if turn.get("sources"):
            with st.expander(f"📚 {len(turn['sources'])} fontes do Vault usadas"):
                for s in turn["sources"]:
                    st.markdown(
                        f"- **{s['path']}** · §{s['section']} "
                        f"(score: {s.get('score', 0):.3f})"
                    )
        st.caption(f"⏱️ {turn['elapsed']:.1f}s · modelo: {turn['model']}")

# ─── Quick-action buttons ────────────────────────────────────────────────────
# Cada botão grava a pergunta correspondente em session_state e dispara um
# rerun. No rerun seguinte, o handler do chat_input pega `pending_q` e roda
# o pipeline normal.
#
# Ordem recomendada: SEMPRE começar pelo diagnóstico — o agente identifica o
# que já existe nos autos e o que falta, evitando regenerar atos já produzidos.
QUICK_ACTIONS = [
    ("📋  Diagnóstico (rode 1º)",
     "Em que fase se encontra esse processo? Identifique o estado FSM atual, "
     "o caminho percorrido e liste os atos já produzidos vs os pendentes.",
     "primary"),
    ("⚖️  Gerar sentença",
     "Gere a minuta da sentença adequada para esse processo, escolhendo o "
     "template correto do Vault.",
     "secondary"),
    ("📂  Expedir documentos faltantes",
     "Expeça todos os documentos faltantes para concluir esse procedimento, "
     "conforme os modelos do Vault. Não regenere atos já produzidos.",
     "secondary"),
]

st.caption(
    "💡 **Sempre rode o diagnóstico primeiro.** Ele lista o que já está "
    "nos autos e o que falta — evita que o agente regenere documentos já produzidos."
)

cols = st.columns(len(QUICK_ACTIONS))
for col, (label, prompt, btn_type) in zip(cols, QUICK_ACTIONS):
    if col.button(label, use_container_width=True, key=f"qa-{label}", type=btn_type):
        st.session_state["pending_q"] = prompt
        st.rerun()

# ─── Input ───────────────────────────────────────────────────────────────────
typed = st.chat_input("Pergunte algo sobre o processo ou o procedimento CEJUSC Pré...")
question = typed or st.session_state.pop("pending_q", None)
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        with placeholder.container():
            st.info(
                "🔍 Buscando no Vault... ⚙️ Chamando o modelo... "
                "(análise grande pode levar até 5 min em CPU-only)"
            )
        t0 = time.time()
        try:
            # Convert UI history into the message format the analyzer expects.
            chat_history = []
            for h in st.session_state.history:
                chat_history.append({"role": "user", "content": h["q"]})
                chat_history.append({"role": "assistant", "content": h["a"]})
            result = asyncio.run(
                analyze(
                    question,
                    pdf_text=st.session_state.get("pdf_text"),
                    history=chat_history,
                )
            )
            elapsed = time.time() - t0
            placeholder.markdown(result.answer)
            with st.expander(f"📚 {len(result.sources)} fontes do Vault usadas"):
                for s in result.sources:
                    st.markdown(
                        f"- **{s['path']}** · §{s['section']} "
                        f"(score: {s.get('score', 0):.3f})"
                    )
            st.caption(f"⏱️ {elapsed:.1f}s · modelo: {result.model}")
            st.session_state.history.append({
                "q": question,
                "a": result.answer,
                "sources": result.sources,
                "elapsed": elapsed,
                "model": result.model,
            })
        except Exception as e:
            elapsed = time.time() - t0
            placeholder.error(f"❌ Falha após {elapsed:.1f}s: {e}")
