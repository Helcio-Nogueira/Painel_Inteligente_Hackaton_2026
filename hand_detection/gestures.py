"""Classificação de gestos a partir dos 21 landmarks MediaPipe (mão espelhada / selfie)."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any


class Gesture(Enum):
    NONE = "none"
    THUMB_UP = "thumb_up"  # novidades
    PEACE = "peace"  # carrinho
    OPEN_PALM = "open_palm"  # notícias
    FIST = "fist"  # voltar
    INDEX_POINT = "index_point"  # registrar rosto (apenas indicador)
    PINCH_OK = "pinch_ok"  # 👌 A-OK (referência visual) — Novidades + olhar no produto


def _dist(a: Any, b: Any) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _finger_extended(lm: list, tip: int, pip: int) -> bool:
    wrist = lm[0]
    return _dist(lm[tip], wrist) > _dist(lm[pip], wrist) * 1.08


# Webcam 2D: polegar+indicador no “O” — com postura tipo emoji ficamos um pouco abaixo do máximo antigo.
OK_CONTACT_MAX = 0.48


def _thumb_index_contact_metric(lm: list) -> float:
    """
    Menor distância entre polegar e indicador (vários pares de landmarks).
    No 👌 / pinça da referência as pontas podem parecer separadas na projeção 2D.
    """
    return min(
        _dist(lm[4], lm[8]),
        _dist(lm[4], lm[7]),
        _dist(lm[3], lm[8]),
        _dist(lm[3], lm[7]),
        _dist(lm[4], lm[6]),
        _dist(lm[3], lm[6]),
        _dist(lm[2], lm[8]),  # base do polegar ↔ ponta do indicador
        _dist(lm[4], lm[5]),  # ponta do polegar ↔ base do indicador
    )


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


def _ok_three_fingers_up_like_emoji(lm: list) -> bool:
    """
    Como o emoji 👌: médio, anelar e mindinho esticados; eixo “para cima” na selfie.
    O médio define a postura; anelar/mindinho podem variar um pouco em y.
    """
    w = lm[0]
    if not _finger_extended(lm, 12, 10):
        return False
    # Referência vertical: ponta do médio acima do punho (mão tipo emoji, não tombada)
    if lm[12].y >= w.y - 0.014:
        return False
    for tip, pip in ((16, 14), (20, 18)):
        if not _finger_extended(lm, tip, pip):
            return False
        if lm[tip].y > w.y + 0.028:
            return False
    return True


def _ok_sign_reference_gesture(lm: list) -> bool:
    """
    Pinça / 👌 estilo emoji: O entre polegar e indicador + três dedos de trás para cima.
    Rejeita punho (dedos recolhidos) e postura com a mão tombada (dedos apontando para baixo).
    """
    if thumb_is_true_thumbs_up(lm):
        return False

    c = _thumb_index_contact_metric(lm)
    if c > OK_CONTACT_MAX:
        return False

    # Punho: todas as pontas longínquas coladas ao punho — às vezes confundia com pinça 2D
    tips_far = [_dist(lm[t], lm[0]) for t in (8, 12, 16, 20)]
    if max(tips_far) < 0.13:
        return False

    if not _ok_three_fingers_up_like_emoji(lm):
        return False

    # Indicador forma o “O”: não é palma aberta com os quatro esticados e afastados do polegar
    i_ext = _finger_extended(lm, 8, 6)
    if i_ext and c > 0.22 and _dist(lm[4], lm[8]) > 0.09:
        return False

    return True


def classify_hand(lm: list) -> Gesture:
    t, i, m, r, p = finger_bools(lm)

    # 👌 A-OK (referência) antes da palma aberta
    if _ok_sign_reference_gesture(lm):
        return Gesture.PINCH_OK

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

    # 5) Apenas indicador estendido (registrar rosto) — não confundir com pinça
    if i and not m and not r and not p and not t and _dist(lm[4], lm[8]) > 0.07:
        return Gesture.INDEX_POINT

    return Gesture.NONE


def pinch_candidate_any_hand(hand_landmarks_list: list) -> bool:
    """True se alguma mão satisfaz o detector de 👌 neste frame (feedback imediato no HUD)."""
    if not hand_landmarks_list:
        return False
    for lm in hand_landmarks_list:
        if _ok_sign_reference_gesture(list(lm)):
            return True
    return False


def pinch_contact_metric_largest_hand(hand_landmarks_list: list) -> float | None:
    """Para HUD: valor da métrica de contato na mão maior (quanto menor, mais “fechado” o O)."""
    if not hand_landmarks_list:
        return None
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
        return None
    return _thumb_index_contact_metric(list(best))


def classify_from_result(hand_landmarks_list: list) -> Gesture:
    """
    👌: testa todas as mãos (o gesto pode estar na mão menor na imagem).
    Demais gestos: mão com maior área na imagem.
    """
    if not hand_landmarks_list:
        return Gesture.NONE
    best = None
    best_area = -1.0
    for lm in hand_landmarks_list:
        hl = list(lm)
        if _ok_sign_reference_gesture(hl):
            return Gesture.PINCH_OK
        xs = [p.x for p in lm]
        ys = [p.y for p in lm]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best_area = area
            best = lm
    if best is None:
        return Gesture.NONE
    return classify_hand(list(best))
