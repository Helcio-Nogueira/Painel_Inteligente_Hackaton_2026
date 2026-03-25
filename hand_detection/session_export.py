"""Exporta um resumo da sessão da loja para o assistente de análise (JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def session_summary_path() -> Path:
    return Path(__file__).resolve().parent / "last_session_summary.json"


def write_session_summary(
    *,
    ended_reason: str,
    user_label: str | None,
    cart_product_ids: list[str],
    mood_seconds: dict[str, float],
    depth_seconds: dict[str, float],
    screen_seconds: dict[str, float],
    look_product_seconds: dict[str, float],
    look_cart_item_seconds: dict[str, float],
    last_screen: str,
) -> Path:
    path = session_summary_path()
    # Mapa de produtos para o texto do assistente (id → nome curto)
    product_labels = {
        "aura": "Fones Aura Pro",
        "fitneo": "Pulseira Fit Neo",
        "caneca": "Caneca térmica Glow",
        "lamp": "Lâmpada smart Aura",
    }

    payload = {
        "ended_reason": ended_reason,
        "user_label": user_label,
        "cart_product_ids": list(cart_product_ids),
        "mood_seconds": {k: round(v, 2) for k, v in mood_seconds.items()},
        "depth_seconds": {k: round(v, 2) for k, v in depth_seconds.items()},
        "screen_seconds": {k: round(v, 2) for k, v in screen_seconds.items()},
        "look_product_seconds": {
            k: {"seconds": round(v, 2), "label": product_labels.get(k, k)}
            for k, v in look_product_seconds.items()
        },
        "look_cart_item_seconds": {k: round(v, 2) for k, v in look_cart_item_seconds.items()},
        "last_screen": last_screen,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
