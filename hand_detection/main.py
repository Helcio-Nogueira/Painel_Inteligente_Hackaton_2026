"""
Duas janelas: câmera com MediaPipe Hands + loja interativa (gestos).

Gestos (mão bem visível, ~0,4 s estáveis):
  🆕 Polegar para cima — Produtos novos
  ✌️ Indicador + médio — Carrinho
  🖐️ Palma aberta (4 dedos) — Notícias
  ✊ Punho — Voltar ao menu (nas telas internas)
  👌 A-OK — polegar e indicador em “O”, outros 3 dedos esticados (Novidades + olhar no produto)

Uso: .venv\\Scripts\\python.exe main.py   ou   run.bat
Q / ESC na janela da câmera: sair.
Sem rosto na câmera por ~5 s (com modelo facial ativo): encerra sozinho.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

from eye_tracker import gaze_from_face_landmarks, gaze_to_screen, get_eye_overlay_points, smooth_gaze
import tkinter as tk
from tkinter import simpledialog

from face_registry import clear_registry, encode_face, recognize_face, register_face_multiple_encodings
from gestures import Gesture, classify_from_result
from store_ui import (
    Screen,
    render_store,
    resolve_carrinho_hover,
    resolve_novidades_hover,
)

# Eye tracking: ponto vermelho na loja indica direção aproximada do olhar (íris).
# Para desativar e voltar ao comportamento anterior: EYE_TRACKING_ENABLED = False
EYE_TRACKING_ENABLED = True

# Conexões entre os 21 pontos (mesmo grafo da solução clássica MediaPipe Hands).
_HAND_PALM = ((0, 1), (0, 5), (9, 13), (13, 17), (5, 9), (0, 17))
_HAND_THUMB = ((1, 2), (2, 3), (3, 4))
_HAND_INDEX = ((5, 6), (6, 7), (7, 8))
_HAND_MIDDLE = ((9, 10), (10, 11), (11, 12))
_HAND_RING = ((13, 14), (14, 15), (15, 16))
_HAND_PINKY = ((17, 18), (18, 19), (19, 20))
HAND_CONNECTIONS: frozenset[tuple[int, int]] = frozenset().union(
    _HAND_PALM, _HAND_THUMB, _HAND_INDEX, _HAND_MIDDLE, _HAND_RING, _HAND_PINKY
)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

WIN_CAM = "Camera — suas maos"
WIN_STORE = "Loja Cap Vivo"
STORE_W, STORE_H = 540, 820

# Encerra o programa se não houver rosto (com modelo facial carregado) por este tempo.
NO_FACE_EXIT_S = 5.0

# Qualidade de frame (valores relaxados para garantir captura)
SHARPNESS_THRESHOLD = 25
MIN_BRIGHTNESS = 25
MIN_FACE_AREA = 0.02  # área do rosto >= 2% da tela
CENTER_TOLERANCE = 0.45  # rosto aceito em boa parte do quadro


def _variance_of_laplacian(frame) -> float:
    """Nitidez: Laplaciano alto = frame nítido."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _frame_brightness(frame) -> float:
    """Brilho médio do frame."""
    return float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))


def _face_bbox_area(lm_list) -> float:
    """Área da bbox do rosto em coords normalizadas (0-1)."""
    xs = [p.x for p in lm_list[:468]]
    ys = [p.y for p in lm_list[:468]]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return w * h


def _face_centered(lm_list) -> bool:
    """Rosto aproximadamente centralizado (centro da bbox perto de 0.5, 0.5)."""
    xs = [p.x for p in lm_list[:468]]
    ys = [p.y for p in lm_list[:468]]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    return abs(cx - 0.5) < CENTER_TOLERANCE and abs(cy - 0.5) < CENTER_TOLERANCE


def check_face_quality(frame, lm_list) -> tuple[bool, str]:
    """
    Verifica se o frame é adequado para registro.
    Retorna (ok, feedback). feedback = mensagem para o usuário.
    """
    if len(lm_list) < 468:
        return False, "Aguardando rosto..."
    sharp = _variance_of_laplacian(frame)
    if sharp < SHARPNESS_THRESHOLD:
        return False, "Mantenha o rosto parado (evite movimento)"
    bright = _frame_brightness(frame)
    if bright < MIN_BRIGHTNESS:
        return False, "Melhore a iluminação"
    area = _face_bbox_area(lm_list)
    if area < MIN_FACE_AREA:
        return False, "Aproxime o rosto da câmera"
    if not _face_centered(lm_list):
        return False, "Mantenha o rosto no centro"
    return True, "Capturando..."


GESTURE_HINT = {
    Gesture.NONE: "Mostre um gesto…",
    Gesture.THUMB_UP: "🆕 Novidades — polegar para cima",
    Gesture.PEACE: "✌️ Carrinho — sinal de paz",
    Gesture.OPEN_PALM: "🖐️ Noticias — palma aberta",
    Gesture.FIST: "🔙 Voltar — punho fechado",
    Gesture.INDEX_POINT: "👆 Registrar rosto — aponte o indicador",
    Gesture.PINCH_OK: "👌 Novidades — A-OK: O com polegar+indicador, médio/anelar/mindinho esticados",
}


def _model_path(name: str) -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local and local.isascii():
            return Path(local) / "CapVivo2026" / "mediapipe_models" / name
    return Path(__file__).resolve().parent / "models" / name


def _ensure_model(path: Path, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > 0:
        return
    print(f"Baixando modelo para {path} ...")
    urllib.request.urlretrieve(url, path)
    print("Download concluído.")


def _draw_eyes(
    frame,
    face_landmarks_list: list | None,
) -> None:
    """Desenha contorno dos olhos e círculos nas íris na janela da câmera."""
    if not face_landmarks_list:
        return
    h, w = frame.shape[:2]
    pts = get_eye_overlay_points(face_landmarks_list, w, h)
    if pts is None:
        return
    left_iris, right_iris, left_contour, right_contour = pts
    # Contorno do olho (verde)
    cv2.polylines(frame, [np.array(left_contour)], True, (80, 255, 120), 1, cv2.LINE_AA)
    cv2.polylines(frame, [np.array(right_contour)], True, (80, 255, 120), 1, cv2.LINE_AA)
    # Íris (círculo verde-água)
    for cx, cy in (left_iris, right_iris):
        cv2.circle(frame, (cx, cy), 6, (0, 255, 200), 2, cv2.LINE_AA)
        cv2.circle(frame, (cx, cy), 2, (255, 255, 255), -1, cv2.LINE_AA)


_FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
_LEFT_BROW = [70, 63, 105, 66, 107]
_RIGHT_BROW = [336, 296, 334, 293, 300]
_NOSE = [168, 6, 197, 195, 5, 4, 1, 19, 94, 2]
_LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]


def _dist(lm, a: int, b: int) -> float:
    pa, pb = lm[a], lm[b]
    return float(np.hypot(pa.x - pb.x, pa.y - pb.y))


def _estimate_mood(lm) -> tuple[str, tuple[int, int, int]]:
    """
    Estimativa simples de humor baseada em sorriso e abertura dos olhos.
    """
    face_h = _dist(lm, 10, 152) + 1e-6
    mouth_w = _dist(lm, 61, 291) / face_h
    mouth_h = _dist(lm, 13, 14) / face_h
    smile_score = mouth_w + mouth_h * 1.8

    left_eye_open = _dist(lm, 159, 145) / (_dist(lm, 33, 133) + 1e-6)
    right_eye_open = _dist(lm, 386, 374) / (_dist(lm, 362, 263) + 1e-6)
    eye_open = (left_eye_open + right_eye_open) * 0.5
    eye_h = (_dist(lm, 159, 145) + _dist(lm, 386, 374)) * 0.5 + 1e-6
    eye_mid_y = (lm[159].y + lm[145].y + lm[386].y + lm[374].y) * 0.25
    iris_mid_y = (lm[468].y + lm[473].y) * 0.5 if len(lm) >= 474 else eye_mid_y
    look_down_score = (iris_mid_y - eye_mid_y) / eye_h

    if look_down_score > 0.22:
        return "Humor: Distraido no celular 📱", (120, 200, 255)

    if smile_score > 0.70 and eye_open > 0.18:
        return "Humor: Feliz 😄", (80, 255, 120)
    if smile_score < 0.56 and eye_open > 0.16:
        return "Humor: Neutro/Serio 😐", (255, 220, 120)
    return "Humor: Relaxado 🙂", (170, 255, 210)


def _blendshape_value(blendshapes, key: str) -> float:
    if not blendshapes:
        return 0.0
    for cat in blendshapes:
        if getattr(cat, "category_name", "") == key:
            return float(getattr(cat, "score", 0.0))
    return 0.0


def _estimate_mood_from_blendshapes(blendshapes) -> tuple[str, tuple[int, int, int]]:
    """
    Estimativa de humor usando blendshapes do MediaPipe Face Landmarker.
    Mais estável para expressão facial do que apenas landmarks.
    """
    smile = (
        _blendshape_value(blendshapes, "mouthSmileLeft")
        + _blendshape_value(blendshapes, "mouthSmileRight")
    ) * 0.5
    frown = (
        _blendshape_value(blendshapes, "mouthFrownLeft")
        + _blendshape_value(blendshapes, "mouthFrownRight")
    ) * 0.5
    blink = (
        _blendshape_value(blendshapes, "eyeBlinkLeft")
        + _blendshape_value(blendshapes, "eyeBlinkRight")
    ) * 0.5
    brow_down = (
        _blendshape_value(blendshapes, "browDownLeft")
        + _blendshape_value(blendshapes, "browDownRight")
    ) * 0.5
    jaw_open = _blendshape_value(blendshapes, "jawOpen")
    look_down = (
        _blendshape_value(blendshapes, "eyeLookDownLeft")
        + _blendshape_value(blendshapes, "eyeLookDownRight")
    ) * 0.5

    if look_down > 0.40:
        return "Humor: Distraido no celular 📱", (120, 200, 255)
    if smile > 0.35 and frown < 0.25:
        return "Humor: Feliz 😄", (80, 255, 120)
    if frown > 0.32 or brow_down > 0.35:
        return "Humor: Serio/Concentrado 😐", (255, 220, 120)
    if jaw_open > 0.45:
        return "Humor: Surpreso 😮", (255, 180, 120)
    return "Humor: Relaxado 🙂", (170, 255, 210)


def _mood_bucket(mood_text: str | None) -> str | None:
    if not mood_text:
        return None
    txt = mood_text.lower()
    if "feliz" in txt:
        return "feliz"
    if "distraido" in txt or "distraído" in txt:
        return "distraido"
    if "serio" in txt or "sério" in txt or "concentrado" in txt:
        return "serio"
    if "surpreso" in txt:
        return "surpreso"
    if "relaxado" in txt:
        return "relaxado"
    return None


def _depth_from_interocular(lm) -> float:
    """Distância interocular normalizada (0–1). Maior ≈ rosto mais perto da câmera."""
    return _dist(lm, 33, 263)


def _depth_category(iod: float) -> tuple[str, str]:
    """
    Categoriza distância aproximada a partir do tamanho do rosto no frame.
    iod em coords normalizadas do MediaPipe.
    """
    if iod >= 0.17:
        return "muito_perto", "Muito perto"
    if iod >= 0.13:
        return "perto", "Perto"
    if iod >= 0.095:
        return "medio", "Media distancia"
    if iod >= 0.065:
        return "longe", "Longe"
    return "muito_longe", "Muito longe"


def _draw_poly_indices(frame, lm, indices: list[int], color: tuple[int, int, int], closed: bool = True, thickness: int = 1) -> None:
    h, w = frame.shape[:2]
    pts = np.array([(int(lm[i].x * w), int(lm[i].y * h)) for i in indices], dtype=np.int32)
    cv2.polylines(frame, [pts], closed, color, thickness, cv2.LINE_AA)


def _draw_face_debug(frame, face_landmarks_list: list | None) -> None:
    """Desenha traços extras do rosto para indicar tracking facial."""
    if not face_landmarks_list:
        return
    lm = face_landmarks_list[0]
    if len(lm) < 468:
        return
    _draw_poly_indices(frame, lm, _FACE_OVAL, (110, 210, 255), True, 1)
    _draw_poly_indices(frame, lm, _LEFT_BROW, (255, 180, 90), False, 2)
    _draw_poly_indices(frame, lm, _RIGHT_BROW, (255, 180, 90), False, 2)
    _draw_poly_indices(frame, lm, _NOSE, (180, 220, 255), False, 1)
    _draw_poly_indices(frame, lm, _LIPS_OUTER, (255, 140, 200), True, 1)


def _draw_hands(
    frame,
    hand_landmarks_list,
    line_color=(0, 255, 180),
    joint_color=(255, 255, 255),
) -> None:
    h, w = frame.shape[:2]
    for landmarks in hand_landmarks_list:
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], line_color, 2, cv2.LINE_AA)
        for x, y in pts:
            cv2.circle(frame, (x, y), 4, joint_color, -1, cv2.LINE_AA)


class StableGesture:
    """Dispara um gesto após N frames iguais; punho tolera poucos frames NONE."""

    def __init__(
        self,
        need: int = 11,
        cooldown: int = 18,
        none_slack_fist: int = 3,
        pinch_need: int = 4,
        pinch_cooldown: int = 10,
    ) -> None:
        self.need = need
        self.cooldown_frames = cooldown
        self.pinch_need = pinch_need
        self.pinch_cooldown = pinch_cooldown
        self.none_slack_fist = none_slack_fist
        self.streak = 0
        self.last: Gesture = Gesture.NONE
        self.cooldown = 0
        self._none_run = 0

    def tick(self, g: Gesture) -> Gesture | None:
        if self.cooldown > 0:
            self.cooldown -= 1
            return None

        effective = g
        if g == Gesture.NONE and self.last == Gesture.FIST and self.streak > 0:
            self._none_run += 1
            if self._none_run <= self.none_slack_fist:
                effective = Gesture.FIST
            else:
                self._none_run = 0
        else:
            self._none_run = 0

        if effective == Gesture.NONE:
            self.streak = 0
            self.last = Gesture.NONE
            return None
        need_frames = (
            self.pinch_need if effective is Gesture.PINCH_OK else self.need
        )
        if effective == self.last:
            self.streak += 1
        else:
            self.streak = 1
            self.last = effective
        if self.streak >= need_frames:
            self.streak = 0
            self.last = Gesture.NONE
            self.cooldown = (
                self.pinch_cooldown
                if effective is Gesture.PINCH_OK
                else self.cooldown_frames
            )
            return effective
        return None


def _apply_navigation(screen: Screen, fired: Gesture) -> Screen:
    if fired is Gesture.PINCH_OK:
        return screen
    if fired is Gesture.FIST and screen is not Screen.MENU and screen is not Screen.REGISTRAR:
        return Screen.MENU
    if fired is Gesture.FIST and screen is Screen.REGISTRAR:
        return Screen.MENU
    if screen is not Screen.MENU and screen is not Screen.REGISTRAR:
        return screen
    if fired is Gesture.THUMB_UP:
        return Screen.NOVIDADES
    if fired is Gesture.PEACE:
        return Screen.CARRINHO
    if fired is Gesture.OPEN_PALM:
        return Screen.NOTICIAS
    if fired is Gesture.INDEX_POINT:
        return Screen.REGISTRAR
    return screen


def _screen_title(s: Screen) -> str:
    return {
        Screen.MENU: "Menu",
        Screen.NOVIDADES: "Novidades",
        Screen.CARRINHO: "Carrinho",
        Screen.NOTICIAS: "Noticias",
        Screen.REGISTRAR: "Registrar",
    }[s]


def main() -> int:
    hand_model = _model_path("hand_landmarker.task")
    _ensure_model(hand_model, MODEL_URL)

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    hand_options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(hand_model)),
        running_mode=VisionRunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    face_landmarker_ctx = None
    try:
        face_model = _model_path("face_landmarker.task")
        _ensure_model(face_model, FACE_MODEL_URL)
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        face_options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(face_model)),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
        )
        face_landmarker_ctx = FaceLandmarker.create_from_options(face_options)
    except Exception as e:
        print(f"Face model nao carregado (eye + registro): {e}", file=sys.stderr)
        face_landmarker_ctx = None

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("Não foi possível abrir a câmera (índice 0).", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Duas janelas: câmera + loja. Q ou ESC na câmera para sair.")

    clear_registry()

    t0 = time.perf_counter()
    screen = Screen.MENU
    # Pinça/👌: menos frames que punho/paz + cooldown curto para repetir compra
    stable = StableGesture(need=7, cooldown=14, pinch_need=3, pinch_cooldown=8)
    first_layout = True
    gaze_smoothed: tuple[float, float] | None = None
    current_user_name: str | None = None
    register_countdown: float | None = None
    register_countdown_start: float | None = None
    register_encodings: list[list[float]] = []
    register_feedback: str = ""
    mood_text: str | None = None
    mood_color: tuple[int, int, int] = (170, 255, 210)
    mood_seconds = {
        "feliz": 0.0,
        "distraido": 0.0,
        "serio": 0.0,
        "surpreso": 0.0,
        "relaxado": 0.0,
    }
    depth_seconds = {
        "muito_perto": 0.0,
        "perto": 0.0,
        "medio": 0.0,
        "longe": 0.0,
        "muito_longe": 0.0,
    }
    depth_iod_smooth: float | None = None
    depth_key_curr: str | None = None
    depth_label_curr: str = ""
    cart_product_ids: list[str] = []
    last_loop_t = time.perf_counter()
    novidades_hover_sticky_id: str | None = None
    novidades_hover_sticky_until: float = 0.0
    carrinho_hover_sticky_id: str | None = None
    carrinho_hover_sticky_until: float = 0.0
    no_face_accum_s = 0.0

    with HandLandmarker.create_from_options(hand_options) as landmarker:
        try:
            while True:
                now_loop = time.perf_counter()
                dt = max(0.0, now_loop - last_loop_t)
                last_loop_t = now_loop
                ok, frame = cap.read()
                if not ok:
                    print("Falha ao ler frame.", file=sys.stderr)
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int((time.perf_counter() - t0) * 1000)
                result = landmarker.detect_for_video(mp_image, ts_ms)

                gaze_xy = None
                face_landmarks_for_draw: list | None = None
                face_blendshapes_for_mood = None
                if face_landmarker_ctx is not None:
                    try:
                        face_result = face_landmarker_ctx.detect_for_video(mp_image, ts_ms)
                        face_landmarks_for_draw = face_result.face_landmarks
                        face_blendshapes_for_mood = getattr(face_result, "face_blendshapes", None)
                        if EYE_TRACKING_ENABLED:
                            raw = gaze_from_face_landmarks(face_landmarks_for_draw)
                            gaze_smoothed = smooth_gaze(gaze_smoothed, raw)
                            gaze_xy = gaze_to_screen(gaze_smoothed, STORE_W, STORE_H)
                    except Exception:
                        pass

                if face_landmarker_ctx is not None:
                    has_face = bool(
                        face_landmarks_for_draw and len(face_landmarks_for_draw) > 0
                    )
                    if has_face:
                        no_face_accum_s = 0.0
                    else:
                        no_face_accum_s += dt
                        if no_face_accum_s >= NO_FACE_EXIT_S:
                            print(
                                "Encerrando: nenhum rosto detectado por "
                                f"{NO_FACE_EXIT_S:.0f} s.",
                                file=sys.stderr,
                            )
                            break

                gesture = classify_from_result(result.hand_landmarks)
                hover_product_id: str | None = None
                hover_carrinho_id: str | None = None
                if screen is Screen.NOVIDADES:
                    hov = resolve_novidades_hover(gaze_xy, STORE_W, STORE_H)
                    if hov:
                        novidades_hover_sticky_id = hov
                        novidades_hover_sticky_until = now_loop + 0.65
                    hover_product_id = hov or (
                        novidades_hover_sticky_id
                        if now_loop < novidades_hover_sticky_until
                        else None
                    )
                    carrinho_hover_sticky_id = None
                    carrinho_hover_sticky_until = 0.0
                elif screen is Screen.CARRINHO:
                    novidades_hover_sticky_id = None
                    novidades_hover_sticky_until = 0.0
                    hov_c = resolve_carrinho_hover(
                        gaze_xy, STORE_W, STORE_H, cart_product_ids
                    )
                    if hov_c:
                        carrinho_hover_sticky_id = hov_c
                        carrinho_hover_sticky_until = now_loop + 0.65
                    hover_carrinho_id = hov_c or (
                        carrinho_hover_sticky_id
                        if now_loop < carrinho_hover_sticky_until
                        else None
                    )
                else:
                    novidades_hover_sticky_id = None
                    novidades_hover_sticky_until = 0.0
                    carrinho_hover_sticky_id = None
                    carrinho_hover_sticky_until = 0.0

                fired = stable.tick(gesture)
                pinch_target_id = hover_product_id
                if (
                    fired is Gesture.PINCH_OK
                    and screen is Screen.NOVIDADES
                    and pinch_target_id
                    and pinch_target_id not in cart_product_ids
                ):
                    cart_product_ids.append(pinch_target_id)
                elif (
                    fired is Gesture.PINCH_OK
                    and screen is Screen.CARRINHO
                    and hover_carrinho_id
                ):
                    try:
                        cart_product_ids.remove(hover_carrinho_id)
                    except ValueError:
                        pass
                elif fired is not None:
                    screen = _apply_navigation(screen, fired)
                    if screen is Screen.MENU and register_countdown_start is not None:
                        register_countdown_start = None
                        register_countdown = None

                # Reconhecimento / saudação (apenas quando há face na tela)
                if face_landmarks_for_draw and len(face_landmarks_for_draw) > 0:
                    lm_list = face_landmarks_for_draw[0]
                    if len(lm_list) >= 468 and screen is not Screen.REGISTRAR:
                        rec = recognize_face(list(lm_list))
                        current_user_name = rec if rec else "Visitante 1"
                    if face_blendshapes_for_mood and len(face_blendshapes_for_mood) > 0:
                        mood_text, mood_color = _estimate_mood_from_blendshapes(face_blendshapes_for_mood[0])
                    elif len(lm_list) >= 468:
                        mood_text, mood_color = _estimate_mood(lm_list)
                else:
                    current_user_name = None
                    mood_text = None

                mood_key = _mood_bucket(mood_text)
                if mood_key is not None and dt < 0.5:
                    mood_seconds[mood_key] += dt

                # Profundidade relativa (proxy pela distância entre olhos no frame)
                depth_key_curr = None
                depth_label_curr = ""
                if face_landmarks_for_draw and len(face_landmarks_for_draw) > 0:
                    lm_d = face_landmarks_for_draw[0]
                    if len(lm_d) >= 468:
                        iod = _depth_from_interocular(lm_d)
                        a = 0.28
                        if depth_iod_smooth is None:
                            depth_iod_smooth = iod
                        else:
                            depth_iod_smooth = depth_iod_smooth * (1.0 - a) + iod * a
                        depth_key_curr, depth_label_curr = _depth_category(depth_iod_smooth)
                        if depth_key_curr is not None and dt < 0.5:
                            depth_seconds[depth_key_curr] += dt
                else:
                    depth_iod_smooth = None

                # Fluxo de registro na tela REGISTRAR
                if screen is Screen.REGISTRAR and face_landmarks_for_draw and len(face_landmarks_for_draw) > 0:
                    lm_list = face_landmarks_for_draw[0]
                    if len(lm_list) >= 468:
                        REGISTER_DURATION = 5.0
                        now = time.perf_counter()
                        quality_ok, register_feedback = check_face_quality(frame, list(lm_list))
                        if register_countdown_start is None:
                            register_countdown_start = now
                            register_encodings.clear()
                        if quality_ok:
                            elapsed = now - register_countdown_start
                            register_countdown = max(0.0, REGISTER_DURATION - elapsed)
                            if len(register_encodings) < 25:
                                enc = encode_face(list(lm_list))
                                if enc:
                                    register_encodings.append(enc)
                        else:
                            register_countdown = REGISTER_DURATION if register_countdown_start else None
                        if register_countdown <= 0:
                            encodings_to_save = list(register_encodings)
                            if not encodings_to_save:
                                enc = encode_face(list(lm_list))
                                if enc:
                                    encodings_to_save = [enc]
                            if encodings_to_save:
                                root = tk.Tk()
                                root.withdraw()
                                root.attributes("-topmost", True)
                                name = simpledialog.askstring(
                                    "Nome",
                                    "Digite o nome para este rosto:",
                                    parent=root,
                                )
                                root.destroy()
                                if name is not None and name.strip():
                                    if register_face_multiple_encodings(encodings_to_save, name.strip()):
                                        current_user_name = name.strip()
                            screen = Screen.MENU
                            register_countdown_start = None
                            register_countdown = None
                            register_encodings.clear()
                            register_feedback = ""
                    else:
                        register_countdown_start = None
                        register_countdown = None
                        register_encodings.clear()
                        register_feedback = "Aguardando rosto..."
                else:
                    if screen is Screen.REGISTRAR:
                        register_countdown_start = None
                        register_countdown = None
                        register_encodings.clear()
                        register_feedback = "Posicione seu rosto na câmera"

                hand_count = len(result.hand_landmarks)
                if hand_count:
                    _draw_hands(frame, result.hand_landmarks)

                if face_landmarks_for_draw:
                    _draw_eyes(frame, face_landmarks_for_draw)
                    _draw_face_debug(frame, face_landmarks_for_draw)

                hint = GESTURE_HINT.get(gesture, "")
                fh, fw = frame.shape[:2]
                hud_y = 28
                hud_lh = 26

                cv2.putText(
                    frame,
                    _screen_title(screen),
                    (16, hud_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.72,
                    (40, 255, 200),
                    2,
                    cv2.LINE_AA,
                )
                hud_y += hud_lh
                cv2.putText(
                    frame,
                    hint if hint else "…",
                    (16, hud_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    (180, 220, 255),
                    1,
                    cv2.LINE_AA,
                )
                hud_y += hud_lh
                eyes_str = "Sim" if face_landmarks_for_draw else "Não"
                cv2.putText(
                    frame,
                    f"Maos: {hand_count}  |  Olhos: {eyes_str}",
                    (16, hud_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.62,
                    (200, 200, 255),
                    2,
                    cv2.LINE_AA,
                )
                hud_y += hud_lh
                ges_col = (60, 255, 120) if gesture is Gesture.PINCH_OK else (200, 210, 255)
                cv2.putText(
                    frame,
                    f"Gesto detectado: {gesture.name}",
                    (16, hud_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.62,
                    ges_col,
                    2 if gesture is Gesture.PINCH_OK else 1,
                    cv2.LINE_AA,
                )
                hud_y += hud_lh + 4

                if current_user_name:
                    hello_cam = f"Ola {current_user_name}!"
                    cv2.putText(
                        frame,
                        hello_cam,
                        (max(16, fw - 300), 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (255, 220, 100),
                        2,
                        cv2.LINE_AA,
                    )
                if mood_text:
                    cv2.putText(
                        frame,
                        mood_text,
                        (16, hud_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        mood_color,
                        2,
                        cv2.LINE_AA,
                    )
                    hud_y += 22
                    mood_row = 18
                    for label, key, col in (
                        ("feliz", "feliz", (120, 255, 150)),
                        ("distraido", "distraido", (120, 200, 255)),
                        ("serio", "serio", (255, 220, 140)),
                        ("surpreso", "surpreso", (255, 180, 120)),
                        ("relaxado", "relaxado", (170, 255, 210)),
                    ):
                        cv2.putText(
                            frame,
                            f"{label}: {mood_seconds[key]:.1f}s",
                            (16, hud_y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.48,
                            col,
                            1,
                            cv2.LINE_AA,
                        )
                        hud_y += mood_row
                    hud_y += 6

                if depth_key_curr is not None and depth_iod_smooth is not None:
                    cv2.putText(
                        frame,
                        "Profundidade (estimativa):",
                        (16, hud_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.52,
                        (200, 230, 255),
                        1,
                        cv2.LINE_AA,
                    )
                    hud_y += 22
                    cv2.putText(
                        frame,
                        f"Atual: {depth_label_curr}",
                        (16, hud_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.52,
                        (150, 255, 200),
                        1,
                        cv2.LINE_AA,
                    )
                    hud_y += 24
                    depth_row = 17
                    for txt, col in (
                        (f"muito perto: {depth_seconds['muito_perto']:.1f}s", (255, 150, 180)),
                        (f"perto: {depth_seconds['perto']:.1f}s", (255, 200, 150)),
                        (f"media dist.: {depth_seconds['medio']:.1f}s", (220, 220, 255)),
                        (f"longe: {depth_seconds['longe']:.1f}s", (180, 200, 255)),
                        (f"muito longe: {depth_seconds['muito_longe']:.1f}s", (150, 180, 255)),
                    ):
                        cv2.putText(
                            frame,
                            txt,
                            (16, hud_y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            col,
                            1,
                            cv2.LINE_AA,
                        )
                        hud_y += depth_row

                if screen is not Screen.MENU:
                    back_msg = "🔙 Voltar: punho fechado ~0,4s"
                    cv2.putText(
                        frame,
                        back_msg,
                        (16, fh - 24),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (80, 200, 255),
                        2,
                        cv2.LINE_AA,
                    )
                if screen is Screen.REGISTRAR and register_feedback:
                    cv2.putText(
                        frame,
                        register_feedback,
                        (16, fh - 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (255, 200, 100),
                        2,
                        cv2.LINE_AA,
                    )

                store_frame = render_store(
                    STORE_W, STORE_H, screen, hint, gaze_xy,
                    greeting_name=current_user_name,
                    register_countdown=register_countdown if screen is Screen.REGISTRAR else None,
                    register_feedback=register_feedback if screen is Screen.REGISTRAR else None,
                    novidades_hover_id=hover_product_id if screen is Screen.NOVIDADES else None,
                    cart_product_ids=cart_product_ids,
                    carrinho_hover_id=hover_carrinho_id if screen is Screen.CARRINHO else None,
                )
                cv2.imshow(WIN_CAM, frame)
                cv2.imshow(WIN_STORE, store_frame)
                if first_layout:
                    first_layout = False
                    cv2.moveWindow(WIN_STORE, 48, 36)
                    cv2.moveWindow(WIN_CAM, STORE_W + 80, 36)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q"), 27):
                    break
        finally:
            cap.release()
            if face_landmarker_ctx is not None and hasattr(face_landmarker_ctx, "close"):
                face_landmarker_ctx.close()
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
