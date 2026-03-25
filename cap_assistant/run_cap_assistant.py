"""
1) Sobe a API (Uvicorn) em subprocesso.
2) Abre o assistente numa JANELA no computador (pywebview / WebView2 no Windows),
   no mesmo espírito da câmera + loja — sem depender do navegador externo.

Se pywebview não estiver instalado, volta a abrir o navegador.

Forçar só navegador: CAPVIVO_ASSISTANT_BROWSER=1
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAND_REQ = ROOT.parent / "hand_detection" / "requirements.txt"
APP_PORT = int(os.environ.get("APP_PORT", "8765"))


def _pip_hint() -> str:
    if HAND_REQ.is_file():
        return f'"{sys.executable}" -m pip install -r "{HAND_REQ}"'
    return f'"{sys.executable}" -m pip install -r "{ROOT / "requirements.txt"}"'


def _pause_exit(code: int) -> int:
    if sys.platform == "win32":
        try:
            input("\nPressione Enter para fechar esta janela… ")
        except EOFError:
            pass
    return code


def _wait_api(port: int, timeout_s: float = 30.0) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def _stop_api(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> int:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    print()
    print("=" * 58)
    print("  Cap Vivo — Assistente (janela no computador)")
    print("=" * 58)
    print(f"  Pasta: {ROOT}")
    print(f"  API:   http://127.0.0.1:{APP_PORT}/  (local)")
    print("  Feche a janela do assistente para encerrar.")
    print("  (Navegador externo: defina CAPVIVO_ASSISTANT_BROWSER=1)")
    print("=" * 58)
    print()

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(APP_PORT),
    ]
    api_proc = subprocess.Popen(api_cmd, cwd=str(ROOT))
    time.sleep(0.6)
    if api_proc.poll() is not None:
        print(
            "\n[ERRO] O servidor terminou logo ao iniciar (código",
            api_proc.returncode,
            ").",
            file=sys.stderr,
        )
        if "uvicorn" in str(api_proc.returncode) or api_proc.returncode == 1:
            print("  Causa comum: falta o pacote uvicorn (e outros).", file=sys.stderr)
        print("  Instale tudo no venv da loja:", file=sys.stderr)
        print(f"    {_pip_hint()}", file=sys.stderr)
        return _pause_exit(1)

    if not _wait_api(APP_PORT):
        print("\n[ERRO] A API não respondeu em /health a tempo.", file=sys.stderr)
        _stop_api(api_proc)
        print(f"  {_pip_hint()}", file=sys.stderr)
        return _pause_exit(1)

    url = f"http://127.0.0.1:{APP_PORT}/"

    force_browser = os.environ.get("CAPVIVO_ASSISTANT_BROWSER", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    if not force_browser:
        try:
            import webview
        except ImportError:
            print(
                "[AVISO] pywebview não encontrado — abrindo o navegador.\n"
                f'  Janela própria: "{sys.executable}" -m pip install pywebview\n'
                f"  Ou instale tudo: {_pip_hint()}\n"
            )
            force_browser = True
        else:
            print("Abrindo janela do assistente…\n")
            try:
                webview.create_window(
                    "Cap Vivo — Assistente",
                    url,
                    width=1200,
                    height=880,
                    resizable=True,
                )
                webview.start(debug=False)
            except Exception as e:
                print(f"[ERRO] pywebview: {e}", file=sys.stderr)
                print("Abrindo navegador como alternativa.\n")
                webbrowser.open(url)
                try:
                    code = api_proc.wait()
                except KeyboardInterrupt:
                    code = 0
                _stop_api(api_proc)
                return code
            _stop_api(api_proc)
            return 0

    print(f"Abrindo navegador: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"(Não foi possível abrir o navegador: {e})", file=sys.stderr)
        print(f"  Abra manualmente: {url}\n", file=sys.stderr)

    try:
        return api_proc.wait()
    except KeyboardInterrupt:
        print("\nEncerrando API…")
        return 0
    finally:
        if api_proc.poll() is None:
            _stop_api(api_proc)


if __name__ == "__main__":
    raise SystemExit(main())
