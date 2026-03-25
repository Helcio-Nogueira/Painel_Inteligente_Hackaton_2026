"""WebSocket hub para enviar a análise ao celular em tempo real."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass
class BroadcastMessage:
    kind: str
    text: str
    timestamp_iso: str


class ConnectionHub:
    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last: BroadcastMessage | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.add(ws)
            last = self._last
        if last is not None:
            await ws.send_text(json.dumps(last.__dict__, ensure_ascii=False))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.discard(ws)

    async def broadcast(self, payload: BroadcastMessage) -> None:
        async with self._lock:
            self._last = payload
            conns = list(self._conns)
        if not conns:
            return
        msg = json.dumps(payload.__dict__, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.discard(ws)


hub = ConnectionHub()

