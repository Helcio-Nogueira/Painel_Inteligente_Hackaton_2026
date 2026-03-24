"""
Duas janelas: câmera com MediaPipe Hands + loja interativa (gestos).

Gestos (mão bem visível, ~0,4 s estáveis):
  🆕 Polegar para cima — Produtos novos
  ✌️ Indicador + médio — Carrinho
  🖐️ Palma aberta (4 dedos) — Notícias
  ✊ Punho — Voltar ao menu (nas telas internas)

Uso: .venv\\Scripts\\python.exe main.py   ou   run.bat
Q / ESC na janela da câmera: sair.
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
from store_ui import Screen, render_store

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
    ) -> None:
        self.need = need
        self.cooldown_frames = cooldown
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
        if effective == self.last:
            self.streak += 1
        else:
            self.streak = 1
            self.last = effective
        if self.streak >= self.need:
            self.streak = 0
            self.last = Gesture.NONE
            self.cooldown = self.cooldown_frames
            return effective
        return None


def _apply_navigation(screen: Screen, fired: Gesture) -> Screen:
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
            output_face_blendshapes=False,
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
    stable = StableGesture()
    first_layout = True
    gaze_smoothed: tuple[float, float] | None = None
    current_user_name: str | None = None
    register_countdown: float | None = None
    register_countdown_start: float | None = None
    register_encodings: list[list[float]] = []
    register_feedback: str = ""

    with HandLandmarker.create_from_options(hand_options) as landmarker:
        try:
            while True:
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
                if face_landmarker_ctx is not None:
                    try:
                        face_result = face_landmarker_ctx.detect_for_video(mp_image, ts_ms)
                        face_landmarks_for_draw = face_result.face_landmarks
                        if EYE_TRACKING_ENABLED:
                            raw = gaze_from_face_landmarks(face_landmarks_for_draw)
                            gaze_smoothed = smooth_gaze(gaze_smoothed, raw)
                            gaze_xy = gaze_to_screen(gaze_smoothed, STORE_W, STORE_H)
                    except Exception:
                        pass

                gesture = classify_from_result(result.hand_landmarks)
                fired = stable.tick(gesture)
                if fired is not None:
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
                else:
                    current_user_name = None

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

                hint = GESTURE_HINT.get(gesture, "")
                cv2.putText(
                    frame,
                    f"{_screen_title(screen)}  |  {hint}",
                    (16, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (40, 255, 200),
                    2,
                    cv2.LINE_AA,
                )
                eyes_str = "Sim" if face_landmarks_for_draw else "Não"
                cv2.putText(
                    frame,
                    f"Maos: {hand_count}  |  Olhos: {eyes_str}",
                    (16, 68),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (200, 200, 255),
                    2,
                    cv2.LINE_AA,
                )
                fh, fw = frame.shape[:2]
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

                if current_user_name:
                    hello_cam = f"Ola {current_user_name}!"
                    cv2.putText(
                        frame,
                        hello_cam,
                        (frame.shape[1] - 280, 36),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (255, 220, 100),
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
