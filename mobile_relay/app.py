from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Cap Vivo — Mobile Relay", version="1.0.0")

_latest_text: str = "Nenhuma análise ainda."
_call_message: str = ""


class TextInput(BaseModel):
    text: str


class CallInput(BaseModel):
    message: str


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


@app.post("/call")
async def call_attendant(data: CallInput) -> dict:
    global _call_message
    _call_message = (data.message or "").strip()
    return {"ok": True}


@app.post("/call/clear")
async def clear_call() -> dict:
    global _call_message
    _call_message = ""
    return {"ok": True}


@app.get("/call/status")
async def call_status() -> dict:
    return {"active": bool(_call_message), "message": _call_message}


@app.get("/atendente", response_class=HTMLResponse)
async def attendant_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cap Vivo — Atendente</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; background:#0b1220; color:#fff; margin:0; padding:18px; display:flex; flex-direction:column; align-items:center; min-height:100vh;}
    h1{font-size:20px; margin:0 0 18px 0; text-align:center;}
    .card{background:#111a2e; border:1px solid #223256; border-radius:14px; padding:24px 20px; width:100%; max-width:400px; text-align:center; font-size:16px; line-height:1.5; transition:all .4s ease;}
    .card.active{border-color:#f59e0b; background:#1a1500; animation:pulse 1.5s infinite;}
    .card.idle{border-color:#223256; color:#7a8baa;}
    .badge{display:inline-block; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; margin-bottom:12px;}
    .badge.active{background:#f59e0b; color:#000;}
    .badge.idle{background:#223256; color:#7a8baa;}
    .msg{font-size:18px; margin-top:8px;}
    .muted{color:#7a8baa; font-size:12px; margin-top:14px;}
    @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(245,158,11,0.3)} 50%{box-shadow:0 0 20px 6px rgba(245,158,11,0.15)}}
  </style>
</head>
<body>
  <h1>Painel do Atendente</h1>
  <div id="card" class="card idle">
    <div id="badge" class="badge idle">Sem chamados</div>
    <div id="msg" class="msg">Nenhum cliente chamando.</div>
  </div>
  <div class="muted">Atualiza automaticamente. Deixe esta aba aberta.</div>
  <script>
    async function poll(){
      const card = document.getElementById('card');
      const badge = document.getElementById('badge');
      const msg = document.getElementById('msg');
      try{
        const r = await fetch('/call/status');
        const d = await r.json();
        if(d.active){
          card.className='card active';
          badge.className='badge active';
          badge.innerText='CHAMADO ATIVO';
          msg.innerText=d.message;
        }else{
          card.className='card idle';
          badge.className='badge idle';
          badge.innerText='Sem chamados';
          msg.innerText='Nenhum cliente chamando.';
        }
      }catch(e){
        msg.innerText='Erro de conexão: '+e.message;
      }
    }
    setInterval(poll, 1000);
    poll();
  </script>
</body>
</html>
"""
    )


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

