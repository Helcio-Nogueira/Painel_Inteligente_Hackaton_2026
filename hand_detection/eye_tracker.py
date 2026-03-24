"""
Proxy de gaze a partir dos landmarks de íris do MediaPipe Face Landmarker.

Usa a posição da íris **relativa ao olho** (não à face) para reduzir o efeito
do movimento da cabeça e aumentar a sensibilidade ao movimento real do olho.
"""

from __future__ import annotations

from typing import Any

# Íris: 468-472 esquerda, 473-477 direita
_LEFT_IRIS = (468, 469, 470, 471, 472)
_RIGHT_IRIS = (473, 474, 475, 476, 477)

# Contorno do olho para bbox (MediaPipe Face Mesh)
_LEFT_EYE = (33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7)
_RIGHT_EYE = (362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382)


def _avg_iris(lm: list, indices: tuple[int, ...]) -> tuple[float, float]:
    x = sum(lm[i].x for i in indices) / len(indices)
    y = sum(lm[i].y for i in indices) / len(indices)
    return x, y


def _eye_bbox(lm: list, indices: tuple[int, ...]) -> tuple[float, float, float, float]:
    xs = [lm[i].x for i in indices]
    ys = [lm[i].y for i in indices]
    return min(xs), min(ys), max(xs), max(ys)


def _relative_in_bbox(
    px: float, py: float,
    left: float, top: float, right: float, bottom: float,
) -> tuple[float, float]:
    w = max(right - left, 0.02)
    h = max(bottom - top, 0.02)
    rx = (px - left) / w
    ry = (py - top) / h
    return (rx, ry)


def gaze_from_face_landmarks(
    face_landmarks_list: list,
) -> tuple[float, float] | None:
    """
    Retorna (x, y) em [0, 1]: posição relativa da íris DENTRO do olho.
    Quando olhando ao centro ~(0.5, 0.5); olhando esquerda x menor; cima y menor.
    Isola o movimento do olho do movimento da cabeça.
    """
    if not face_landmarks_list:
        return None
    lm = face_landmarks_list[0]
    if len(lm) < 478:
        return None

    l_iris = _avg_iris(lm, _LEFT_IRIS)
    r_iris = _avg_iris(lm, _RIGHT_IRIS)
    l_bbox = _eye_bbox(lm, _LEFT_EYE)
    r_bbox = _eye_bbox(lm, _RIGHT_EYE)

    l_rel = _relative_in_bbox(l_iris[0], l_iris[1], *l_bbox)
    r_rel = _relative_in_bbox(r_iris[0], r_iris[1], *r_bbox)

    gx = (l_rel[0] + r_rel[0]) / 2.0
    gy = (l_rel[1] + r_rel[1]) / 2.0

    return (max(0, min(1, gx)), max(0, min(1, gy)))


def smooth_gaze(
    prev: tuple[float, float] | None,
    curr: tuple[float, float] | None,
    alpha: float = 0.52,
) -> tuple[float, float] | None:
    """Suaviza o ponto de gaze com média móvel exponencial."""
    if curr is None:
        return prev
    if prev is None:
        return curr
    nx = prev[0] + alpha * (curr[0] - prev[0])
    ny = prev[1] + alpha * (curr[1] - prev[1])
    return (nx, ny)


# Calibração do mapeamento gaze → tela
GAZE_SENSITIVITY_X = 3.65  # Horizontal um pouco mais sensível
GAZE_SENSITIVITY_Y_UP = 2.70  # Olhar para cima um pouco mais responsivo
GAZE_SENSITIVITY_Y_DOWN = 1.35  # Olhar para baixo menos agressivo
CENTER_X, CENTER_Y = 0.5, 0.60  # Centro vertical levemente mais baixo
# Curva suave: pequenos movimentos amplificam um pouco mais (evita zona morta no centro)
_POWER = 0.92  # < 1 amplifica perto do centro


def gaze_to_screen(
    gaze: tuple[float, float] | None,
    width: int,
    height: int,
) -> tuple[int, int] | None:
    """
    Converte gaze relativo ao olho (0-1) para coordenadas na janela da loja.
    Aplica sensibilidade e curva suave para melhor resposta ao movimento do olho.
    """
    if gaze is None:
        return None
    gx, gy = gaze

    def _remap(v: float, center: float, sensitivity: float) -> float:
        d = v - center
        sign = 1.0 if d >= 0 else -1.0
        abs_d = abs(d)
        curved = sign * (abs_d ** _POWER)
        return center + curved * sensitivity

    cx = _remap(gx, CENTER_X, GAZE_SENSITIVITY_X)
    # Corrige eixo vertical: olhar para cima deve mover a bolinha para cima.
    gy_inv = 1.0 - gy
    y_sensitivity = GAZE_SENSITIVITY_Y_UP if gy_inv < CENTER_Y else GAZE_SENSITIVITY_Y_DOWN
    cy = _remap(gy_inv, CENTER_Y, y_sensitivity)
    x = max(0, min(width - 1, int(cx * width)))
    y = max(0, min(height - 1, int(cy * height)))
    return (x, y)


def get_eye_overlay_points(
    face_landmarks_list: list,
    frame_w: int,
    frame_h: int,
) -> tuple[tuple[int, int], tuple[int, int], list[tuple[int, int]], list[tuple[int, int]]] | None:
    """
    Retorna (left_iris_center, right_iris_center, left_eye_contour, right_eye_contour)
    em coordenadas de pixel para desenhar no frame.
    """
    if not face_landmarks_list:
        return None
    lm = face_landmarks_list[0]
    if len(lm) < 478:
        return None

    def to_px(x: float, y: float) -> tuple[int, int]:
        return (int(x * frame_w), int(y * frame_h))

    left_iris = _avg_iris(lm, _LEFT_IRIS)
    right_iris = _avg_iris(lm, _RIGHT_IRIS)
    left_contour = [to_px(lm[i].x, lm[i].y) for i in _LEFT_EYE]
    right_contour = [to_px(lm[i].x, lm[i].y) for i in _RIGHT_EYE]

    return (
        to_px(left_iris[0], left_iris[1]),
        to_px(right_iris[0], right_iris[1]),
        left_contour,
        right_contour,
    )
