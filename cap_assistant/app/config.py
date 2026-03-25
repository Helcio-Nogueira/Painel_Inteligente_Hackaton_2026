"""Configurações — baseado no projeto de referência em IAtemporaria/temp_processo_seletivo_cap."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "8765"))

    PAYROLL_DATA_PATH = os.getenv(
        "PAYROLL_DATA_PATH",
        str(_ROOT / "data" / "payroll.csv"),
    )

    WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")

    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    @classmethod
    def validate(cls) -> None:
        """Garante dataset local; chaves de LLM são opcionais (modo demonstração)."""
        if not os.path.isfile(cls.PAYROLL_DATA_PATH):
            raise FileNotFoundError(
                f"Arquivo de folha não encontrado: {cls.PAYROLL_DATA_PATH}"
            )
