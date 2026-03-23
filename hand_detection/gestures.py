"""Classificação de gestos a partir dos 21 landmarks MediaPipe (mão espelhada / selfie)."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any


class Gesture(Enum):
    NONE = "none"
    THUMB_UP = "thumb_up"  # novidades (polegar claro para cima)
    PEACE = "peace"  # carrinho
    OPEN_PALM = "open_palm"  # notícias
    FIST = "fist"  # voltar (punho: sem dedos estendidos)


def _dist(a: Any, b: Any) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _finger_extended(lm: list, tip: int, pip: int) -> bool:
    wrist = lm[0]
    return _dist(lm[tip], wrist) > _dist(lm[pip], wrist) * 1.08


def thumb_is_true_thumbs_up(lm: list) -> bool:
    """
    Polegar “valendo” só quando o gesto é claramente para cima (selfie espelhada).
    No punho o polegar às vezes passa no teste dist(tip)>dist(IP), por isso exigimos
    a ponta acima da articulação IP na imagem (y menor = mais alto na tela).
    """
    tip, ip = lm[4], lm[3]
    if tip.y >= ip.y - 0.014:
        return False
    if _dist(tip, lm[0]) <= _dist(ip, lm[0]) * 1.1:
        return False
    # Polegar afastado do punho (não dobrado sobre a palma)
    if _dist(tip, lm[5]) < 0.065:
        return False
    return True


def finger_bools(lm: list) -> tuple[bool, bool, bool, bool, bool]:
    """thumb (só thumbs-up real), index, middle, ring, pinky."""
    thumb = thumb_is_true_thumbs_up(lm)
    index = _finger_extended(lm, 8, 6)
    middle = _finger_extended(lm, 12, 10)
    ring = _finger_extended(lm, 16, 14)
    pinky = _finger_extended(lm, 20, 18)
    return thumb, index, middle, ring, pinky


def classify_hand(lm: list) -> Gesture:
    t, i, m, r, p = finger_bools(lm)

    # 1) Palma aberta: os quatro dedos longos estendidos (polegar não exige)
    if i and m and r and p:
        return Gesture.OPEN_PALM

    # 2) Paz: indicador + médio; anelar e mindinho recolhidos
    if i and m and not r and not p:
        return Gesture.PEACE

    # 3) Só polegar para cima, demais recolhidos
    if t and not i and not m and not r and not p:
        return Gesture.THUMB_UP

    # 4) Punho: nenhum dedo longo estendido e polegar não é thumbs-up
    if not i and not m and not r and not p and not t:
        return Gesture.FIST

    return Gesture.NONE


def classify_from_result(hand_landmarks_list: list) -> Gesture:
    """Usa a mão com maior bounding box (mais próxima / visível)."""
    if not hand_landmarks_list:
        return Gesture.NONE
    best = None
    best_area = -1.0
    for lm in hand_landmarks_list:
        xs = [p.x for p in lm]
        ys = [p.y for p in lm]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best_area = area
            best = lm
    if best is None:
        return Gesture.NONE
    return classify_hand(list(best))
