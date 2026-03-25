"""Interface Streamlit simplificada — sem exportar conversa, sem tema configurável, sem painel de nome/persona."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

API_BASE_URL = os.environ.get("CAP_ASSISTANT_API", "http://127.0.0.1:8765")


def _load_session_summary() -> Optional[dict]:
    raw = os.environ.get("CAPVIVO_SESSION_JSON", "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []


def _history_for_api() -> List[Dict[str, str]]:
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.conversation_history[-12:]
    ]


def send_message(message: str) -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "conversation_history": _history_for_api(),
            },
            timeout=120,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"Não foi possível contactar a API ({API_BASE_URL}): {e}")
        return None


def format_evidence_block(evidence: List[Dict[str, Any]]) -> str:
    if not evidence:
        return ""
    lines: List[str] = []
    for i, ev in enumerate(evidence, 1):
        rec = ev.get("record_data") or {}
        lines.append(
            f"{i}. {rec.get('name', '—')} (ID {ev.get('employee_id', '—')}) — "
            f"competência {ev.get('competency', '—')} — líquido R$ {rec.get('net_pay', '—')}"
        )
    return "\n".join(lines)


st.set_page_config(
    page_title="Assistente — Cap Vivo",
    page_icon="📊",
    layout="wide",
)

_init_state()

st.title("Assistente de análise")
st.caption("Consultas sobre a folha de dados de exemplo e, se existir, o resumo da sessão na loja.")

summary = _load_session_summary()
if summary:
    with st.expander("Resumo da última sessão (loja)", expanded=False):
        st.json(summary)
else:
    st.info(
        "Sem resumo de sessão neste arranque. "
        "Ao sair da loja por ausência de rosto, o JSON é gravado e repassado automaticamente."
    )

with st.sidebar:
    st.subheader("Estado da API")
    try:
        h = requests.get(f"{API_BASE_URL}/health", timeout=3)
        if h.status_code == 200:
            st.success("API disponível")
        else:
            st.warning("API respondeu com erro")
    except requests.RequestException:
        st.error("API indisponível — verifique se o servidor foi iniciado.")

    st.divider()
    st.subheader("Funcionários no dataset")
    try:
        er = requests.get(f"{API_BASE_URL}/employees", timeout=3)
        if er.status_code == 200:
            for name in er.json().get("employees", []):
                st.write(f"• {name}")
        else:
            st.write("Não foi possível listar.")
    except requests.RequestException:
        st.write("—")

    st.divider()
    st.subheader("Exemplos")
    examples = [
        "Quanto recebi em maio/2025? (Ana Souza)",
        "Qual o total líquido de Ana Souza no 1º trimestre de 2025?",
        "Qual foi o desconto de INSS do Bruno Lima em junho/2025?",
    ]
    for i, ex in enumerate(examples):
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.pending_example = ex

    st.divider()
    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.session_state.pop("pending_example", None)
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("evidence"):
            with st.expander("Registros citados"):
                st.text(format_evidence_block(msg["evidence"]))

pending = st.session_state.pop("pending_example", None)
user_text: Optional[str] = None
if pending:
    user_text = pending
elif prompt := st.chat_input("Escreva sua pergunta"):
    user_text = prompt

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_text}
    )

    with st.spinner("A processar…"):
        response = send_message(user_text)

    if response:
        ev = response.get("evidence")
        ev_serial: Optional[List[Dict[str, Any]]]
        if isinstance(ev, list):
            ev_serial = [e for e in ev if isinstance(e, dict)]
        else:
            ev_serial = None
        assistant_msg = response.get("message") or "(Resposta vazia.)"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_msg,
                "evidence": ev_serial,
            }
        )
        st.session_state.conversation_history.append(
            {"role": "assistant", "content": assistant_msg}
        )

    st.rerun()
