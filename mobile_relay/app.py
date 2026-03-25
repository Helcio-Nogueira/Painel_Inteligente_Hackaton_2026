from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Cap Vivo — Mobile Relay", version="1.0.0")

_latest_text: str = "Nenhuma análise ainda."


class TextInput(BaseModel):
    text: str


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/send")
async def send_text(data: TextInput) -> dict:
    global _latest_text
    txt = (data.text or "").strip()
    if not txt:
        raise HTTPException(status_code=400, detail="text vazio")
    _latest_text = txt
    return {"ok": True}


@app.get("/text")
async def get_text() -> dict:
    return {"text": _latest_text}


@app.get("/", response_class=HTMLResponse)
async def mobile_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cap Vivo — Mobile</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; background:#0b1220; color:#fff; margin:0; padding:18px;}
    h1{font-size:18px; margin:0 0 10px 0;}
    .card{background:#111a2e; border:1px solid #223256; border-radius:12px; padding:14px; white-space:pre-wrap; line-height:1.35;}
    .muted{color:#c7d2fe; font-size:12px; margin-top:10px;}
  </style>
</head>
<body>
  <h1>Resumo da IA (tempo real)</h1>
  <div id="content" class="card">Carregando…</div>
  <div class="muted">Deixe esta página aberta. Atualiza automaticamente.</div>
  <script>
    async function load(){
      const el = document.getElementById('content');
      try{
        const res = await fetch('/text');
        if(!res.ok){ throw new Error('HTTP ' + res.status); }
        const data = await res.json();
        el.innerText = data.text || '(vazio)';
      }catch(e){
        el.innerText = 'Sem ligação ao PC (rede/IP/firewall). Abra http://IP_DO_PC:8000/ no mesmo Wi‑Fi ou hotspot. No PC: ipconfig → IPv4. Erro: ' + (e && e.message ? e.message : e);
      }
    }
    setInterval(load, 1000);
    load();
  </script>
</body>
</html>
"""
    )

