"""API FastAPI + interface web (frontend HTML do projeto de referência)."""

from __future__ import annotations

import logging
import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import httpx

from app.config import Config
from app.llm_service import LLMService
from app.models import ChatRequest, ChatResponse
from app.web_search import WebSearchService
from app.ws_hub import BroadcastMessage, hub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Assistente Cap Vivo",
    description="API de chat (LLM opcional) para análise de dados via mensagens",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    Config.validate()
    llm_service = LLMService()
    web_search_service = WebSearchService() if Config.WEB_SEARCH_ENABLED else None
    logger.info("Serviços inicializados.")
except Exception as e:
    logger.error("Erro na inicialização: %s", e)
    raise

_CAP_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND = _CAP_ROOT / "frontend"
_FRONTEND_EXISTS = _FRONTEND.is_dir() and (_FRONTEND / "index.html").is_file()


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "llm_service": "active",
            "web_search": "active" if web_search_service else "disabled",
        },
    }


@app.get("/session_summary")
async def session_summary() -> dict:
    """Lê o JSON gerado pela loja (se fornecido via CAPVIVO_SESSION_JSON)."""
    p = os.environ.get("CAPVIVO_SESSION_JSON", "").strip()
    if not p:
        return {"available": False, "summary": None}
    path = Path(p)
    if not path.is_file():
        return {"available": False, "summary": None}
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
        return {"available": True, "summary": summary}
    except Exception as e:
        return {"available": False, "summary": None, "error": str(e)}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        logger.info("Mensagem: %s...", request.message[:80])
        context = None

        if web_search_service and _is_web_search_query(request.message):
            web_results = web_search_service.search(request.message)
            if web_results:
                web_response = llm_service.generate_response(
                    user_message=(
                        f"{request.message}\n\nInformações auxiliares:\n{web_results}"
                    ),
                    conversation_history=request.conversation_history,
                    extra_context=context,
                )
                return ChatResponse(
                    message=web_response,
                    sources=[web_results.get("source", "Web")],
                    timestamp=datetime.now(),
                )

        response = llm_service.generate_response(
            user_message=request.message,
            conversation_history=request.conversation_history,
            extra_context=context,
        )
        out = ChatResponse(message=response, timestamp=datetime.now())

        # Envia ao "site do celular" (relay) se estiver configurado.
        relay_url = os.environ.get("CAPVIVO_MOBILE_RELAY_URL", "").strip()
        if relay_url:
            try:
                async with httpx.AsyncClient(timeout=1.2) as client:
                    await client.post(
                        relay_url.rstrip("/") + "/send",
                        json={"text": out.message},
                    )
            except Exception:
                pass

        # Envia ao celular imediatamente após gerar a resposta
        try:
            await hub.broadcast(
                BroadcastMessage(
                    kind="analysis",
                    text=out.message,
                    timestamp_iso=out.timestamp.isoformat(),
                )
            )
        except Exception:
            pass
        return out

    except Exception as e:
        logger.error("Erro no chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            # Mantém a conexão viva; ignoramos mensagens do cliente por enquanto.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)


def _is_web_search_query(message: str) -> bool:
    web_keywords = [
        "taxa selic",
        "selic",
        "inflação",
        "inflacao",
        "ibovespa",
        "dólar",
        "dolar",
        "notícias",
        "noticias",
        "economia",
        "clima",
        "temperatura",
    ]
    message_lower = message.lower()
    return any(k in message_lower for k in web_keywords)


# Interface web (README do projeto de referência: abrir o mesmo host no navegador)
if _FRONTEND_EXISTS:

    @app.get("/")
    async def root_index() -> FileResponse:
        return FileResponse(_FRONTEND / "index.html")

    @app.get("/{file_path:path}")
    async def serve_frontend(file_path: str) -> FileResponse:
        allowed = {
            "style.css",
            "script.js",
            "capgemini-logo.png.png",
            "capgemini-icon.png.png",
            "index.html",
            "test.html",
            "capgemini-logo.svg",
            "capgemini-icon.svg",
        }
        if file_path in allowed:
            loc = _FRONTEND / file_path
            if loc.is_file():
                return FileResponse(loc)
        return FileResponse(_FRONTEND / "index.html")


else:

    @app.get("/")
    async def root_json() -> dict:
        return {
            "name": "Assistente Cap Vivo",
            "version": "1.1.0",
            "docs": "/docs",
            "note": "Coloque a pasta frontend/ ao lado de app/ (copie de IAtemporaria/temp_processo_seletivo_cap/frontend).",
        }
