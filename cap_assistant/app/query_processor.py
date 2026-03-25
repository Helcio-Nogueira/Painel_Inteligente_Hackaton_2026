"""Processador de consultas — baseado no projeto de referência."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.models import Evidence
from app.rag_system import PayrollRAG
from app.utils import extract_competency_from_query, extract_employee_name_from_query, format_currency_br


class QueryProcessor:
    def __init__(self, rag_system: PayrollRAG) -> None:
        self.rag = rag_system

    def process_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        query_type = self._identify_query_type(query)
        if query_type == "net_pay":
            return self._process_net_pay_query(query)
        if query_type == "total_period":
            return self._process_total_period_query(query)
        if query_type == "deduction":
            return self._process_deduction_query(query)
        if query_type == "payment_date":
            return self._process_payment_date_query(query)
        if query_type == "max_bonus":
            return self._process_max_bonus_query(query)
        return None, None

    def _identify_query_type(self, query: str) -> str:
        query_normalized = re.sub(r"[\u00ad\u2011\u2013\u2014]", "", query)
        query_lower = query_normalized.lower()

        if any(
            w in query_lower
            for w in ["líquido", "liquido", "lquido", "recebi", "recebeu", "quanto"]
        ):
            if any(
                w in query_lower
                for w in ["trimestre", "período", "periodo", "total", "1º", "primeiro"]
            ):
                return "total_period"
            return "net_pay"

        if "total" in query_lower and (
            "líquido" in query_lower or "liquido" in query_lower or "lquido" in query_lower
        ):
            if any(
                w in query_lower
                for w in ["trimestre", "período", "periodo", "1º", "primeiro"]
            ):
                return "total_period"

        if "total" in query_lower and "l" in query_lower and "quido" in query_lower:
            if any(
                w in query_lower
                for w in ["trimestre", "período", "periodo", "1º", "primeiro"]
            ):
                return "total_period"

        if any(w in query_lower for w in ["inss", "irrf", "desconto"]):
            return "deduction"
        if any(w in query_lower for w in ["quando", "data", "pago"]):
            return "payment_date"
        if any(w in query_lower for w in ["maior", "máximo", "maximo", "bônus", "bonus"]):
            return "max_bonus"
        return "unknown"

    def _process_net_pay_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        employee_name = extract_employee_name_from_query(query)
        competency = extract_competency_from_query(query)
        if not employee_name or not competency:
            return (
                "Informe o nome do funcionário e a competência (ex.: maio/2025) para consultar o líquido.",
                None,
            )
        result = self.rag.get_net_pay(employee_name, competency)
        if not result:
            return f"Não há dados para {employee_name} na competência {competency}.", None
        net_pay, evidence = result
        response = f"O salário líquido de {employee_name} em {competency} foi {format_currency_br(net_pay)}."
        return response, [evidence]

    def _process_total_period_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        employee_name = extract_employee_name_from_query(query)
        if not employee_name:
            return "Informe o nome do funcionário para calcular o total do período.", None
        period = self._extract_period_from_query(query)
        if not period:
            return "Especifique o período (ex.: 1º trimestre de 2025).", None
        start_comp, end_comp = period
        result = self.rag.get_total_period(employee_name, start_comp, end_comp)
        if not result:
            return f"Não há dados para {employee_name} nesse intervalo.", None
        total, evidence_list = result
        response = (
            f"O total líquido de {employee_name} entre {start_comp} e {end_comp} "
            f"foi {format_currency_br(total)}."
        )
        return response, evidence_list

    def _process_deduction_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        employee_name = extract_employee_name_from_query(query)
        competency = extract_competency_from_query(query)
        if not employee_name or not competency:
            return "Informe funcionário e competência para consultar descontos.", None
        deduction_type = "irrf" if "irrf" in query.lower() else "inss"
        result = self.rag.get_deduction(employee_name, competency, deduction_type)
        if not result:
            return f"Não há dados para {employee_name} em {competency}.", None
        deduction_value, evidence = result
        response = (
            f"O desconto de {deduction_type.upper()} de {employee_name} em {competency} "
            f"foi {format_currency_br(deduction_value)}."
        )
        return response, [evidence]

    def _process_payment_date_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        employee_name = extract_employee_name_from_query(query)
        competency = extract_competency_from_query(query)
        if not employee_name or not competency:
            return "Informe funcionário e competência para a data de pagamento.", None
        result = self.rag.get_payment_date(employee_name, competency)
        if not result:
            return f"Não há dados para {employee_name} em {competency}.", None
        payment_date, evidence = result
        net_pay = evidence.record_data["net_pay"]
        response = (
            f"Pagamento de {employee_name} em {competency}: {payment_date}, "
            f"valor líquido {format_currency_br(float(net_pay))}."
        )
        return response, [evidence]

    def _process_max_bonus_query(self, query: str) -> Tuple[Optional[str], Optional[List[Evidence]]]:
        employee_name = extract_employee_name_from_query(query)
        if not employee_name:
            return "Informe o nome do funcionário para consultar o maior bônus.", None
        result = self.rag.get_max_bonus(employee_name)
        if not result:
            return f"Não há dados para {employee_name}.", None
        max_bonus, competency, evidence = result
        response = f"O maior bônus de {employee_name} foi {format_currency_br(max_bonus)} (competência {competency})."
        return response, [evidence]

    def _extract_period_from_query(self, query: str) -> Optional[Tuple[str, str]]:
        query_normalized = re.sub(r"[\u00ad\u2011\u2013\u2014]", "", query)
        query_lower = query_normalized.lower()
        if (
            "1º trimestre" in query_lower
            or "primeiro trimestre" in query_lower
            or ("1" in query_lower and "trimestre" in query_lower)
        ):
            return ("2025-01", "2025-03")
        if "2º trimestre" in query_lower or "segundo trimestre" in query_lower:
            return ("2025-04", "2025-06")
        if "janeiro" in query_lower and ("março" in query_lower or "marco" in query_lower):
            return ("2025-01", "2025-03")
        return None
