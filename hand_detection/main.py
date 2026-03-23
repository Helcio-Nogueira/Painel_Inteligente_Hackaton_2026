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
import mediapipe as mp

from gestures import Gesture, classify_from_result
from store_ui import Screen, render_store

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

WIN_CAM = "Camera — suas maos"
WIN_STORE = "Loja Cap Vivo"
STORE_W, STORE_H = 540, 820

GESTURE_HINT = {
    Gesture.NONE: "Mostre um gesto…",
    Gesture.THUMB_UP: "🆕 Novidades — polegar para cima",
    Gesture.PEACE: "✌️ Carrinho — sinal de paz",
    Gesture.OPEN_PALM: "🖐️ Noticias — palma aberta",
    Gesture.FIST: "🔙 Voltar — punho fechado",
}


def _model_path() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local and local.isascii():
            return Path(local) / "CapVivo2026" / "mediapipe_models" / "hand_landmarker.task"
    return Path(__file__).resolve().parent / "models" / "hand_landmarker.task"


def _ensure_model(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > 0:
        return
    print(f"Baixando modelo para {path} ...")
    urllib.request.urlretrieve(MODEL_URL, path)
    print("Download concluído.")


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
    if fired is Gesture.FIST and screen is not Screen.MENU:
        return Screen.MENU
    if screen is not Screen.MENU:
        return screen
    if fired is Gesture.THUMB_UP:
        return Screen.NOVIDADES
    if fired is Gesture.PEACE:
        return Screen.CARRINHO
    if fired is Gesture.OPEN_PALM:
        return Screen.NOTICIAS
    return screen


def _screen_title(s: Screen) -> str:
    return {
        Screen.MENU: "Menu",
        Screen.NOVIDADES: "Novidades",
        Screen.CARRINHO: "Carrinho",
        Screen.NOTICIAS: "Noticias",
    }[s]


def main() -> int:
    model_path = _model_path()
    _ensure_model(model_path)

    BaseOptions = mp.tasks.BaseOptions
    HandLandmarker = mp.tasks.vision.HandLandmarker
    HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=VisionRunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("Não foi possível abrir a câmera (índice 0).", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Duas janelas: câmera + loja. Q ou ESC na câmera para sair.")

    t0 = time.perf_counter()
    screen = Screen.MENU
    stable = StableGesture()
    first_layout = True

    with HandLandmarker.create_from_options(options) as landmarker:
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

                gesture = classify_from_result(result.hand_landmarks)
                fired = stable.tick(gesture)
                if fired is not None:
                    screen = _apply_navigation(screen, fired)

                hand_count = len(result.hand_landmarks)
                if hand_count:
                    _draw_hands(frame, result.hand_landmarks)

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
                cv2.putText(
                    frame,
                    f"Maos: {hand_count}",
                    (16, 68),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (200, 200, 255),
                    2,
                    cv2.LINE_AA,
                )
                if screen is not Screen.MENU:
                    fh, fw = frame.shape[:2]
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

                store_frame = render_store(STORE_W, STORE_H, screen, hint)
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
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
