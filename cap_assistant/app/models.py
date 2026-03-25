"""Modelos Pydantic — alinhados ao projeto de referência."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class PayrollRecord(BaseModel):
    employee_id: str
    name: str
    competency: str
    base_salary: float
    bonus: float
    benefits_vt_vr: float
    other_earnings: float
    deductions_inss: float
    deductions_irrf: float
    other_deductions: float
    net_pay: float
    payment_date: str


class Evidence(BaseModel):
    employee_id: str
    competency: str
    record_data: dict[str, Any]
    source_line: int


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None
    evidence: Optional[List[Evidence]] = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    message: str
    evidence: Optional[List[Evidence]] = None
    sources: Optional[List[str]] = None
    timestamp: datetime


class PayrollQuery(BaseModel):
    employee_name: Optional[str] = None
    employee_id: Optional[str] = None
    competency: Optional[str] = None
    query_type: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
