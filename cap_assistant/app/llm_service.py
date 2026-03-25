"""Integração LLM — baseado no projeto de referência; tom e identidade neutros (configurável depois)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

from app.config import Config
from app.models import ChatMessage, Evidence
from app.utils import format_currency_br, parse_date_br


class LLMService:
    def __init__(self) -> None:
        if Config.OPENAI_API_KEY and Config.OPENAI_API_KEY not in (
            "your_openai_api_key_here",
            "",
        ):
            self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            self.openai_client = None
        self.model = Config.OPENAI_MODEL
        self.groq_api_key = Config.GROQ_API_KEY or ""

    def generate_response(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        evidence: Optional[List[Evidence]] = None,
        extra_context: str | None = None,
    ) -> str:
        if (
            not Config.OPENAI_API_KEY
            or Config.OPENAI_API_KEY == "your_openai_api_key_here"
            or Config.OPENAI_API_KEY == "demo_mode"
        ) and not Config.GROQ_API_KEY:
            return self._demo_response(user_message, evidence)

        if Config.GROQ_API_KEY and Config.GROQ_API_KEY != "your_groq_api_key_here":
            try:
                return self._groq_response(user_message, conversation_history, evidence, extra_context)
            except Exception as e:
                print(f"Erro no Groq: {e}")
                if self.openai_client:
                    try:
                        return self._openai_response(user_message, conversation_history, evidence, extra_context)
                    except Exception as e2:
                        print(f"Erro no OpenAI: {e2}")
                        return self._demo_response(user_message, evidence)
                return self._demo_response(user_message, evidence)

        if self.openai_client:
            try:
                return self._openai_response(user_message, conversation_history, evidence, extra_context)
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    return self._demo_response(user_message, evidence)
                return f"Erro ao processar a mensagem: {e}"

        return self._demo_response(user_message, evidence)

    def _groq_response(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        evidence: Optional[List[Evidence]] = None,
        extra_context: str | None = None,
    ) -> str:
        messages = self._build_conversation_context(user_message, conversation_history, evidence, extra_context)
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "messages": messages,
            "model": "llama-3.1-8b-instant",
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def _openai_response(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        evidence: Optional[List[Evidence]] = None,
        extra_context: str | None = None,
    ) -> str:
        if not self.openai_client:
            raise RuntimeError("Cliente OpenAI não inicializado")
        messages = self._build_conversation_context(user_message, conversation_history, evidence, extra_context)
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        return (response.choices[0].message.content or "").strip()

    def _build_conversation_context(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        evidence: Optional[List[Evidence]] = None,
        extra_context: str | None = None,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._get_system_prompt()},
        ]
        if extra_context:
            messages.append({"role": "system", "content": f"Contexto de dados:\n{extra_context}"})
        if conversation_history:
            for msg in conversation_history[-5:]:
                messages.append({"role": msg.role, "content": msg.content})
        if evidence:
            evidence_text = self._format_evidence(evidence)
            user_message = f"{user_message}\n\nDados relevantes:\n{evidence_text}"
        messages.append({"role": "user", "content": user_message})
        return messages

    def _get_system_prompt(self) -> str:
        return """Você é um assistente de análise de dados.
Sua função é identificar padrões, inconsistências, tendências e relações em bases tabulares (ex.: CSV) que serão fornecidas pelo usuário/cliente.

Regras de resposta:
- Responda em português brasileiro, com linguagem clara, objetiva e profissional.
- Baseie-se prioritariamente no **Contexto de dados** fornecido (colunas, tipos, ausências, amostra).
- Quando fizer sentido, devolva: hipóteses, evidências, limitações, e próximos passos de validação.
- Não assuma domínio (financeiro, saúde, etc.) sem o usuário indicar; não rotule a IA.
- Se a pergunta exigir uma coluna que não existe ou dados que não foram carregados, explique o que falta e proponha como obter."""

    def _format_evidence(self, evidence: List[Evidence]) -> str:
        if not evidence:
            return ""
        parts: List[str] = []
        for ev in evidence:
            record = ev.record_data
            parts.append(
                f"Funcionário: {record['name']} (ID: {ev.employee_id})\n"
                f"Competência: {ev.competency}\n"
                f"Salário base: {format_currency_br(float(record['base_salary']))}\n"
                f"Bônus: {format_currency_br(float(record['bonus']))}\n"
                f"INSS: {format_currency_br(float(record['deductions_inss']))}\n"
                f"IRRF: {format_currency_br(float(record['deductions_irrf']))}\n"
                f"Líquido: {format_currency_br(float(record['net_pay']))}\n"
                f"Pagamento: {parse_date_br(str(record['payment_date']))}\n"
                f"Referência: {ev.employee_id}, {ev.competency}"
            )
        return "\n\n".join(parts)

    def _demo_response(
        self, user_message: str, evidence: Optional[List[Evidence]] = None
    ) -> str:
        message_lower = user_message.lower()
        if evidence:
            if "líquido" in message_lower or "liquido" in message_lower:
                return (
                    "Resultado a partir do dataset local (modo sem chave de API): "
                    + self._format_evidence(evidence)
                )
            if "inss" in message_lower:
                return "INSS conforme registros: " + self._format_evidence(evidence)
            if "bônus" in message_lower or "bonus" in message_lower:
                return "Bônus conforme registros: " + self._format_evidence(evidence)
            return "Dados utilizados: " + self._format_evidence(evidence)
        if "selic" in message_lower:
            return (
                "Consulta externa não executada neste modo. "
                "Verifique fontes oficiais (ex.: Banco Central) ou configure uma chave de API."
            )
        return (
            "Modo demonstração: sem chave OpenAI/Groq configurada. "
            f"Mensagem recebida: «{user_message}». "
            "Configure OPENAI_API_KEY ou GROQ_API_KEY no arquivo .env desta pasta para respostas geradas."
        )

    def is_payroll_query(self, message: str) -> bool:
        payroll_keywords = [
            "salário",
            "salario",
            "pagamento",
            "líquido",
            "liquido",
            "bônus",
            "bonus",
            "inss",
            "irrf",
            "desconto",
            "descontos",
            "folha",
            "competência",
            "competencia",
            "recebi",
            "recebeu",
            "quanto",
            "valor",
            "data",
            "quando",
            "funcionário",
            "funcionario",
            "maior",
            "máximo",
            "maximo",
            "total",
            "trimestre",
            "período",
            "periodo",
        ]
        message_normalized = (
            message.replace("\u00ad", "")
            .replace("\u2011", "")
            .replace("\u2013", "")
            .replace("\u2014", "")
        )
        message_lower = message_normalized.lower()
        return any(keyword in message_lower for keyword in payroll_keywords)
