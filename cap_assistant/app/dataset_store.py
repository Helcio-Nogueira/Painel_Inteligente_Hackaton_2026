"""Armazenamento simples de dataset em memória (processo local).

Objetivo: permitir que a UI carregue um CSV do cliente e o assistente analise padrões.
Não há persistência em disco e não há multiusuário: é um processo local por sessão.

Nota: o fluxo atual do `app.api` não importa este módulo; mantido para evolução futura.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


@dataclass
class DatasetState:
    name: str
    loaded_at_utc: str
    rows: int
    cols: int
    columns: list[str]
    dtypes: dict[str, str]


_df: pd.DataFrame | None = None
_state: DatasetState | None = None


def has_dataset() -> bool:
    return _df is not None and _state is not None


def get_state() -> DatasetState | None:
    return _state


def get_df() -> pd.DataFrame | None:
    return _df


def load_csv_bytes(content: bytes, *, name: str = "dataset.csv") -> DatasetState:
    global _df, _state
    bio = io.BytesIO(content)
    df = pd.read_csv(bio)
    _df = df
    _state = DatasetState(
        name=name,
        loaded_at_utc=datetime.now(timezone.utc).isoformat(),
        rows=int(df.shape[0]),
        cols=int(df.shape[1]),
        columns=[str(c) for c in df.columns.tolist()],
        dtypes={str(k): str(v) for k, v in df.dtypes.astype(str).to_dict().items()},
    )
    return _state


def dataset_profile_text(max_cols: int = 60, max_rows_sample: int = 8) -> str:
    """Resumo textual curto para dar contexto ao LLM."""
    if _df is None or _state is None:
        return "Nenhum dataset carregado."

    df = _df
    cols = _state.columns[:max_cols]
    df2 = df[cols] if cols and len(cols) < len(df.columns) else df

    missing = (df2.isna().mean() * 100.0).sort_values(ascending=False)
    top_missing = missing.head(min(12, len(missing)))

    num_df = df2.select_dtypes(include=["number"])
    corr_txt = ""
    if num_df.shape[1] >= 2:
        corr = num_df.corr(numeric_only=True).abs()
        pairs: list[tuple[str, str, float]] = []
        for i, a in enumerate(corr.columns):
            for b in corr.columns[i + 1 :]:
                v = float(corr.loc[a, b])
                if v >= 0.7:
                    pairs.append((str(a), str(b), v))
        pairs.sort(key=lambda x: x[2], reverse=True)
        if pairs:
            corr_txt = "\nCorrelações fortes (|r|>=0,70):\n" + "\n".join(
                f"- {a} × {b}: {v:.2f}" for a, b, v in pairs[:10]
            )

    sample = df2.head(max_rows_sample).to_markdown(index=False)

    return (
        f"Dataset: {_state.name}\n"
        f"Linhas: {_state.rows} | Colunas: {_state.cols}\n"
        f"Colunas (parcial): {', '.join(map(str, cols))}"
        + ("\n(Existem mais colunas; resumo truncado.)" if len(cols) < _state.cols else "")
        + "\n\nTipos:\n"
        + "\n".join(f"- {k}: {v}" for k, v in list(_state.dtypes.items())[:max_cols])
        + "\n\nValores ausentes (% por coluna — top 12):\n"
        + "\n".join(f"- {k}: {v:.1f}%" for k, v in top_missing.items())
        + corr_txt
        + "\n\nAmostra (primeiras linhas):\n"
        + sample
    )

