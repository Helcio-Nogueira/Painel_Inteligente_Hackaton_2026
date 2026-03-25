"""Sistema RAG para folha de pagamento — baseado no projeto de referência."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

import pandas as pd

from app.models import Evidence, PayrollRecord
from app.utils import parse_competency, parse_date_br


def _record_dump(record: PayrollRecord) -> dict:
    return record.model_dump()


class PayrollRAG:
    def __init__(self, data_path: str) -> None:
        self.data_path = data_path
        self.df = self._load_data()
        self._preprocess_data()

    def _load_data(self) -> pd.DataFrame:
        try:
            return pd.read_csv(self.data_path)
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar dados: {e}") from e

    def _preprocess_data(self) -> None:
        self.df["payment_date"] = pd.to_datetime(self.df["payment_date"])
        self.df["competency_formatted"] = self.df["competency"].apply(
            lambda x: f"{x[:4]}-{x[5:7]}"
        )
        self.df["name_normalized"] = self.df["name"].str.lower().str.strip()
        self.df["source_line"] = self.df.index + 2

    def search_employee(self, name: str) -> List[PayrollRecord]:
        name_clean = re.sub(r"[^\w\s]", "", name.lower().strip())

        exact_matches = self.df[self.df["name_normalized"] == name_clean]
        if not exact_matches.empty:
            return self._df_to_records(exact_matches)

        partial_matches = self.df[
            self.df["name_normalized"].str.contains(name_clean, case=False, na=False)
        ]
        if not partial_matches.empty:
            return self._df_to_records(partial_matches)

        for word in name_clean.split():
            if len(word) > 2:
                word_matches = self.df[
                    self.df["name_normalized"].str.contains(word, case=False, na=False)
                ]
                if not word_matches.empty:
                    return self._df_to_records(word_matches)
        return []

    def search_by_competency(self, competency: str) -> List[PayrollRecord]:
        parsed_comp = parse_competency(competency)
        if not parsed_comp:
            return []
        matches = self.df[self.df["competency"] == parsed_comp]
        return self._df_to_records(matches)

    def search_employee_competency(self, name: str, competency: str) -> List[PayrollRecord]:
        employees = self.search_employee(name)
        if not employees:
            return []
        parsed_comp = parse_competency(competency)
        if not parsed_comp:
            return []
        return [emp for emp in employees if emp.competency == parsed_comp]

    def get_net_pay(self, name: str, competency: str) -> Optional[Tuple[float, Evidence]]:
        records = self.search_employee_competency(name, competency)
        if not records:
            return None
        record = records[0]
        evidence = Evidence(
            employee_id=record.employee_id,
            competency=record.competency,
            record_data=_record_dump(record),
            source_line=self._get_source_line(record.employee_id, record.competency),
        )
        return record.net_pay, evidence

    def get_total_period(
        self, name: str, start_comp: str, end_comp: str
    ) -> Optional[Tuple[float, List[Evidence]]]:
        employees = self.search_employee(name)
        if not employees:
            return None
        start_parsed = parse_competency(start_comp)
        end_parsed = parse_competency(end_comp)
        if not start_parsed or not end_parsed:
            return None
        period_records = [emp for emp in employees if start_parsed <= emp.competency <= end_parsed]
        if not period_records:
            return None
        total = sum(emp.net_pay for emp in period_records)
        evidence_list = [
            Evidence(
                employee_id=r.employee_id,
                competency=r.competency,
                record_data=_record_dump(r),
                source_line=self._get_source_line(r.employee_id, r.competency),
            )
            for r in period_records
        ]
        return total, evidence_list

    def get_deduction(
        self, name: str, competency: str, deduction_type: str
    ) -> Optional[Tuple[float, Evidence]]:
        records = self.search_employee_competency(name, competency)
        if not records:
            return None
        record = records[0]
        deduction_value = getattr(record, f"deductions_{deduction_type.lower()}", 0)
        evidence = Evidence(
            employee_id=record.employee_id,
            competency=record.competency,
            record_data=_record_dump(record),
            source_line=self._get_source_line(record.employee_id, record.competency),
        )
        return float(deduction_value), evidence

    def get_payment_date(self, name: str, competency: str) -> Optional[Tuple[str, Evidence]]:
        records = self.search_employee_competency(name, competency)
        if not records:
            return None
        record = records[0]
        payment_date = parse_date_br(record.payment_date)
        evidence = Evidence(
            employee_id=record.employee_id,
            competency=record.competency,
            record_data=_record_dump(record),
            source_line=self._get_source_line(record.employee_id, record.competency),
        )
        return payment_date, evidence

    def get_max_bonus(self, name: str) -> Optional[Tuple[float, str, Evidence]]:
        employees = self.search_employee(name)
        if not employees:
            return None
        max_bonus = 0.0
        max_record: PayrollRecord | None = None
        for emp in employees:
            if emp.bonus > max_bonus:
                max_bonus = emp.bonus
                max_record = emp
        if max_record is None:
            return None
        evidence = Evidence(
            employee_id=max_record.employee_id,
            competency=max_record.competency,
            record_data=_record_dump(max_record),
            source_line=self._get_source_line(max_record.employee_id, max_record.competency),
        )
        return max_bonus, max_record.competency, evidence

    def _df_to_records(self, df: pd.DataFrame) -> List[PayrollRecord]:
        records: List[PayrollRecord] = []
        for _, row in df.iterrows():
            records.append(
                PayrollRecord(
                    employee_id=row["employee_id"],
                    name=row["name"],
                    competency=row["competency"],
                    base_salary=float(row["base_salary"]),
                    bonus=float(row["bonus"]),
                    benefits_vt_vr=float(row["benefits_vt_vr"]),
                    other_earnings=float(row["other_earnings"]),
                    deductions_inss=float(row["deductions_inss"]),
                    deductions_irrf=float(row["deductions_irrf"]),
                    other_deductions=float(row["other_deductions"]),
                    net_pay=float(row["net_pay"]),
                    payment_date=str(row["payment_date"]),
                )
            )
        return records

    def _get_source_line(self, employee_id: str, competency: str) -> int:
        mask = (self.df["employee_id"] == employee_id) & (self.df["competency"] == competency)
        matches = self.df[mask]
        if not matches.empty:
            return int(matches.iloc[0]["source_line"])
        return 0
