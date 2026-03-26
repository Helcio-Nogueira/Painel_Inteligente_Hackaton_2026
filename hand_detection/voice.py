"""Módulo de voz — TTS via SAPI5 (win32com) + STT via Whisper (Groq).

TTS: SAPI.SpVoice direto via COM, numa thread dedicada.
STT: grava com sounddevice → envia WAV para Groq Whisper API.
Monitor de áudio: thread de fundo que mede nível do mic em tempo real.
"""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import time
import wave

import numpy as np
import sounddevice as sd

# ---------------------------------------------------------------------------
# Detecção automática do microfone real
# ---------------------------------------------------------------------------

_mic_device: int | None = None


def _find_real_mic() -> int | None:
    """Testa dispositivos de entrada e retorna o primeiro que captura áudio real."""
    global _mic_device
    if _mic_device is not None:
        return _mic_device

    devs = sd.query_devices()
    candidates: list[int] = []
    for i, d in enumerate(devs):
        if d["max_input_channels"] < 1:
            continue
        name = d["name"].lower()
        if "realtek" in name or "mic in" in name or "microphone array" in name:
            candidates.insert(0, i)
        elif "iriun" not in name and "virtual" not in name:
            candidates.append(i)

    for idx in candidates:
        try:
            ch = min(devs[idx]["max_input_channels"], 2)
            test = sd.rec(
                int(0.3 * 16000), samplerate=16000, channels=ch,
                dtype="int16", device=idx,
            )
            sd.wait()
            energy = float(np.abs(test.astype(np.float32)).mean())
            name = devs[idx]["name"]
            print(f"[voice] Testando mic [{idx}] {name} (ch={ch}): energia={energy:.0f}")
            if energy > 3:
                print(f"[voice] Microfone selecionado: [{idx}] {name}")
                _mic_device = idx
                return idx
        except Exception as e:
            print(f"[voice] Mic [{idx}] falhou: {e}")
            continue

    default_idx = sd.default.device[0]
    if default_idx is not None and isinstance(default_idx, int):
        print(f"[voice] Nenhum mic com áudio — usando default [{default_idx}]")
        _mic_device = default_idx
        return default_idx

    return None


# ---------------------------------------------------------------------------
# Monitor de áudio em tempo real (para barra na câmera)
# ---------------------------------------------------------------------------

_audio_level: float = 0.0
_audio_level_lock = threading.Lock()
_monitor_running = False
_monitor_stopped = threading.Event()


def _audio_monitor_worker() -> None:
    """Lê o microfone continuamente e atualiza _audio_level (RMS normalizado 0-1)."""
    global _audio_level, _monitor_running
    _monitor_running = True
    _monitor_stopped.clear()
    dev = _find_real_mic()
    devs = sd.query_devices()
    ch = min(devs[dev]["max_input_channels"], 2) if dev is not None else 1
    chunk = int(0.05 * 16000)

    def _callback(indata, frames, t_info, status):
        global _audio_level
        rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
        level = min(1.0, rms / 250.0)
        with _audio_level_lock:
            _audio_level = level

    try:
        with sd.InputStream(
            samplerate=16000, channels=ch, dtype="int16",
            device=dev, blocksize=chunk, callback=_callback,
        ):
            while _monitor_running:
                time.sleep(0.05)
    except Exception as e:
        print(f"[voice] Monitor de áudio falhou: {e}", file=sys.stderr)
    finally:
        _monitor_stopped.set()


def start_audio_monitor() -> None:
    """Inicia o monitor de nível de áudio em background."""
    t = threading.Thread(target=_audio_monitor_worker, daemon=True)
    t.start()


def _pause_monitor() -> None:
    """Para o monitor temporariamente para liberar o dispositivo."""
    global _monitor_running
    if _monitor_running:
        _monitor_running = False
        _monitor_stopped.wait(timeout=2.0)
        time.sleep(0.15)


def _resume_monitor() -> None:
    """Reinicia o monitor após gravação."""
    start_audio_monitor()


def stop_audio_monitor() -> None:
    global _monitor_running
    _monitor_running = False


def get_audio_level() -> float:
    """Retorna nível de áudio atual (0.0 a 1.0) para desenhar na câmera."""
    with _audio_level_lock:
        return _audio_level


# ---------------------------------------------------------------------------
# Fila e thread TTS
# ---------------------------------------------------------------------------

_tts_queue: queue.Queue[tuple[str, threading.Event | None] | None] = queue.Queue()
_tts_thread: threading.Thread | None = None
_tts_lock = threading.Lock()


def _tts_worker() -> None:
    """Thread dedicada: inicializa COM, cria voz SAPI e consome a fila."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    speaker = None
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Rate = 1
        voices = speaker.GetVoices()
        for i in range(voices.Count):
            v = voices.Item(i)
            desc = v.GetDescription().lower()
            if "brazil" in desc or "maria" in desc or "daniel" in desc:
                speaker.Voice = v
                print(f"[voice] Voz selecionada: {v.GetDescription()}")
                break
    except Exception as e:
        print(f"[voice] SAPI indisponível: {e}", file=sys.stderr)
        speaker = None

    while True:
        item = _tts_queue.get()
        if item is None:
            break
        text, done_evt = item
        if speaker is not None:
            try:
                speaker.Speak(text)
            except Exception as e:
                print(f"[voice] Erro TTS: {e}", file=sys.stderr)
        else:
            print(f"[voice] (sem TTS) {text}")
        if done_evt is not None:
            done_evt.set()
        _tts_queue.task_done()

    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


def _ensure_thread() -> None:
    global _tts_thread
    with _tts_lock:
        if _tts_thread is None or not _tts_thread.is_alive():
            _tts_thread = threading.Thread(target=_tts_worker, daemon=True)
            _tts_thread.start()


def speak(text: str) -> None:
    """Enfileira texto para ser falado em background (não bloqueia)."""
    _ensure_thread()
    _tts_queue.put((text, None))


def speak_and_wait(text: str) -> None:
    """Enfileira texto e aguarda até ser falado (bloqueia a thread chamante)."""
    _ensure_thread()
    done = threading.Event()
    _tts_queue.put((text, done))
    done.wait()


def shutdown() -> None:
    """Para a thread de TTS e o monitor."""
    stop_audio_monitor()
    try:
        _tts_queue.put(None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Escuta (STT via sounddevice + Groq Whisper)
# ---------------------------------------------------------------------------

def _load_groq_key() -> str | None:
    """Carrega GROQ_API_KEY do .env do cap_assistant."""
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), "..", "cap_assistant", ".env")
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GROQ_API_KEY=") and not line.endswith("="):
                    return line.split("=", 1)[1].strip()
    return None


def _transcribe_whisper_groq(wav_path: str) -> str | None:
    """Envia WAV para Groq Whisper API e retorna texto."""
    key = _load_groq_key()
    if not key:
        print("[voice] GROQ_API_KEY não encontrada — Whisper indisponível.", file=sys.stderr)
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        with open(wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                language="pt",
            )
        text = result.text.strip() if result.text else None
        if text:
            print(f"[voice] Whisper reconheceu: {text}")
        return text
    except Exception as e:
        print(f"[voice] Erro Whisper/Groq: {e}", file=sys.stderr)
        return None


def _transcribe_google_fallback(wav_path: str) -> str | None:
    """Fallback: tenta Google STT via speech_recognition."""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="pt-BR")
        if text:
            print(f"[voice] Google reconheceu: {text}")
        return text.strip() if text else None
    except Exception:
        return None


def listen(duration: float = 5.0) -> str | None:
    """Grava o microfone por `duration` segundos e transcreve via Whisper (Groq)."""
    _pause_monitor()

    dev = _find_real_mic()
    devs = sd.query_devices()
    ch = min(devs[dev]["max_input_channels"], 2) if dev is not None else 1
    time.sleep(0.3)

    sample_rate = 16000
    print(f"[voice] Gravando {duration}s com mic [{dev}] (ch={ch})… (fale agora)")
    try:
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=ch,
            dtype="int16",
            device=dev,
        )
        sd.wait()
    except Exception as e:
        print(f"[voice] Erro ao gravar: {e}", file=sys.stderr)
        _resume_monitor()
        return None

    if ch > 1:
        audio = audio[:, 0:1]

    # Amplifica o sinal para não precisar gritar
    gain = 12
    audio_f = audio.astype(np.float32) * gain
    audio = np.clip(audio_f, -32768, 32767).astype(np.int16)

    energy = float(np.abs(audio.astype(np.float32)).mean())
    print(f"[voice] Energia do áudio (amplificado {gain}x): {energy:.0f}")

    _resume_monitor()

    if energy < 15:
        print("[voice] Áudio muito silencioso.", file=sys.stderr)
        return None

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_fd)
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        text = _transcribe_whisper_groq(tmp_path)
        if text:
            return text

        text = _transcribe_google_fallback(tmp_path)
        if text:
            return text

        print("[voice] Nenhum motor de STT conseguiu reconhecer.", file=sys.stderr)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Greeting (background — câmera abre na hora)
# ---------------------------------------------------------------------------

_voice_name: str | None = None
_voice_name_lock = threading.Lock()


_MENU_EXPLANATION = (
    "Este é o menu. "
    "Para ver os produtos novos, faça um joinha. "
    "Para abrir o carrinho, faça o sinal da paz. "
    "Para ver notícias, abra a palma da mão. "
    "Para registrar seu rosto, aponte o dedo indicador. "
    "Agora é com você!"
)


def _greeting_worker() -> None:
    """Thread do greeting: pergunta nome → grava 5s → responde → explica menu."""
    global _voice_name

    speak_and_wait("Olá, tudo bem? Qual é o seu nome?")
    name = listen(duration=3)

    if name:
        with _voice_name_lock:
            _voice_name = name
        speak_and_wait(f"Prazer, {name}!")
        speak(_MENU_EXPLANATION)
    else:
        speak_and_wait("Não entendi o nome, mas tudo bem.")
        speak(_MENU_EXPLANATION)


def start_greeting() -> None:
    """Inicia o greeting em background (não bloqueia — câmera abre na hora)."""
    global _last_narrated_screen
    _last_narrated_screen = "MENU"
    t = threading.Thread(target=_greeting_worker, daemon=True)
    t.start()


def get_voice_name() -> str | None:
    """Retorna o nome capturado por voz (ou None se ainda não ouviu / falhou)."""
    with _voice_name_lock:
        return _voice_name


# ---------------------------------------------------------------------------
# Narração de telas e ações
# ---------------------------------------------------------------------------

_PRODUCT_LABELS: dict[str, str] = {
    "aura": "Fones Aura Pro",
    "fitneo": "Pulseira Fit Neo",
    "caneca": "Caneca térmica Glow",
    "lamp": "Lâmpada smart Aura",
}

_ALL_PRODUCT_IDS = ["aura", "fitneo", "caneca", "lamp"]

_last_narrated_screen: str | None = None
_last_narrated_product: str | None = None


def narrate_screen_change(screen_name: str, cart_product_ids: list[str] | None = None) -> None:
    """Fala a descrição da tela quando ela muda, incluindo conteúdo dinâmico."""
    global _last_narrated_screen, _last_narrated_product
    if screen_name == _last_narrated_screen:
        return
    _last_narrated_screen = screen_name
    _last_narrated_product = None

    if screen_name == "MENU":
        speak(
            "Você está no menu principal. "
            "Joinha para produtos, paz para carrinho, "
            "palma aberta para notícias, indicador para registrar rosto."
        )

    elif screen_name == "NOVIDADES":
        produtos_texto = ". ".join(
            f"Produto {i + 1}: {_PRODUCT_LABELS[pid]}"
            for i, pid in enumerate(_ALL_PRODUCT_IDS)
        )
        speak(
            f"Você está na seção de produtos. "
            f"Os destaques de hoje são: {produtos_texto}. "
        )
        speak(
            "Para selecionar o produto 1, faça 1 com a mão. "
            "Para o produto 2, faça 2. "
            "Para o produto 3, faça 3. "
            "Para o produto 4, abra a palma da mão. "
            "Você também pode olhar para um produto e fazer o gesto de OK. "
            "Feche o punho para voltar ao menu."
        )

    elif screen_name == "CARRINHO":
        if cart_product_ids:
            itens = ", ".join(
                _PRODUCT_LABELS.get(pid, pid) for pid in cart_product_ids
            )
            speak(
                f"Você está no carrinho. "
                f"Seus itens: {itens}. "
                f"Olhe para um item e faça OK para removê-lo. "
                f"Feche o punho para voltar."
            )
        else:
            speak(
                "Você está no carrinho, mas ele está vazio. "
                "Feche o punho para voltar ao menu e adicione produtos."
            )

    elif screen_name == "NOTICIAS":
        speak(
            "Você está na seção de notícias. "
            "Feche o punho para voltar ao menu."
        )

    elif screen_name == "REGISTRAR":
        speak(
            "Vamos registrar seu rosto. "
            "Fique parado e olhe para a câmera."
        )


def narrate_product_hover(product_id: str | None) -> None:
    """Fala o nome do produto se o hover mudou."""
    global _last_narrated_product
    if product_id == _last_narrated_product:
        return
    _last_narrated_product = product_id
    if product_id:
        label = _PRODUCT_LABELS.get(product_id, product_id)
        speak(f"Você está olhando para {label}.")


def narrate_cart_add(product_id: str) -> None:
    label = _PRODUCT_LABELS.get(product_id, product_id)
    speak(f"Você colocou {label} no carrinho.")


def narrate_cart_remove(product_id: str) -> None:
    label = _PRODUCT_LABELS.get(product_id, product_id)
    speak(f"{label} removido do carrinho.")


def narrate_goodbye() -> None:
    speak("Obrigado pela visita! Até a próxima.")
