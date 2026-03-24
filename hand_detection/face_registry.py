"""
Registro e reconhecimento de rostos a partir dos landmarks do MediaPipe.

Usa os 468 pontos do face mesh (normalizados) como "impressão" do rosto.
Salva múltiplos encodings por pessoa para reconhecimento mais robusto.
Dados apagados ao iniciar o programa (sessão em memória ou limpa no start).
"""

from __future__ import annotations

import math

# Índices dos centros dos olhos para normalização (escala)
_LEFT_EYE = (33, 133, 159, 145, 158, 173, 153, 144)
_RIGHT_EYE = (362, 263, 386, 374, 385, 380, 373, 390)
_NUM_LANDMARKS = 468
_KEYPOINTS = (
    1, 4, 6, 9, 10, 33, 46, 61, 70, 78, 93, 105, 127, 132, 133, 152, 172, 199,
    234, 263, 267, 291, 300, 323, 334, 356, 362, 389, 397, 454,
)
_PAIR_FEATURES = (
    (33, 263),   # distância entre olhos
    (61, 291),   # largura da boca
    (152, 10),   # altura do rosto
    (127, 356),  # largura da face
    (4, 152),    # nariz -> queixo
)

# Registry em memória (limpa ao iniciar; opcionalmente persiste durante sessão)
_registry: list[dict] = []


def _eye_center(lm: list, indices: tuple[int, ...]) -> tuple[float, float]:
    xs = [lm[i].x for i in indices]
    ys = [lm[i].y for i in indices]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _encode_face(face_landmarks: list) -> list[float] | None:
    """
    Gera vetor normalizado dos 468 landmarks (x,y) para comparação.
    Centra no centróide e escala pela distância interocular.
    """
    if len(face_landmarks) < _NUM_LANDMARKS:
        return None
    lm = list(face_landmarks)[:_NUM_LANDMARKS]

    left = _eye_center(lm, _LEFT_EYE)
    right = _eye_center(lm, _RIGHT_EYE)
    scale = math.hypot(right[0] - left[0], right[1] - left[1])
    if scale < 0.01:
        return None

    # Sistema de coordenadas alinhado pelos olhos (reduz efeito de rotação/pose)
    ox = (left[0] + right[0]) * 0.5
    oy = (left[1] + right[1]) * 0.5
    ux = (right[0] - left[0]) / scale
    uy = (right[1] - left[1]) / scale
    vx = -uy
    vy = ux

    vec: list[float] = []
    for idx in _KEYPOINTS:
        p = lm[idx]
        dx = p.x - ox
        dy = p.y - oy
        # projeções no eixo dos olhos e eixo perpendicular + profundidade
        px = (dx * ux + dy * uy) / 1.0
        py = (dx * vx + dy * vy) / 1.0
        pz = p.z / scale
        vec.extend((px, py, pz))

    # Razões geométricas estáveis
    for a, b in _PAIR_FEATURES:
        pa, pb = lm[a], lm[b]
        d = math.sqrt((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2)
        vec.append(d / scale)

    # Normaliza vetor para comparação por cosseno
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < 1e-8:
        return None
    vec = [v / norm for v in vec]
    return vec


def _distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return float("inf")
    # Distância cosseno: 0 = igual, 2 = oposto
    dot = sum(x * y for x, y in zip(a, b))
    return 1.0 - max(-1.0, min(1.0, dot))


def clear_registry() -> None:
    """Limpa o registro de rostos (chamado ao iniciar o programa)."""
    global _registry
    _registry = []


def encode_face(face_landmarks: list) -> list[float] | None:
    """Gera vetor normalizado dos 468 landmarks para comparação."""
    return _encode_face(face_landmarks)


def register_face(face_landmarks: list, name: str) -> bool:
    """Registra um rosto com o nome. Retorna True se sucesso."""
    enc = _encode_face(face_landmarks)
    if enc is None:
        return False
    return register_face_by_encoding(enc, name)


def register_face_by_encoding(encoding: list[float], name: str) -> bool:
    """Registra um encoding com o nome."""
    if not encoding:
        return False
    global _registry
    _registry.append({"name": name.strip() or "Visitante", "encoding": encoding})
    return True


def _mean_encoding(encodings: list[list[float]]) -> list[float] | None:
    if not encodings:
        return None
    n, dim = len(encodings), len(encodings[0])
    if any(len(e) != dim for e in encodings):
        return None
    return [sum(e[i] for e in encodings) / n for i in range(dim)]


def register_face_multiple_encodings(encodings: list[list[float]], name: str) -> bool:
    """
    Registra vários encodings para a mesma pessoa.
    Inclui a média dos encodings (mais robusto) e cada um individualmente.
    """
    if not encodings:
        return False
    name = name.strip() or "Visitante"
    global _registry
    mean_enc = _mean_encoding(encodings)
    if mean_enc:
        _registry.append({"name": name, "encoding": mean_enc})
    for enc in encodings:
        if enc:
            _registry.append({"name": name, "encoding": enc})
    return True


def recognize_face(face_landmarks: list, threshold: float = 0.12) -> str | None:
    """
    Compara o rosto atual com os registrados.
    Retorna o nome do melhor match ou None.
    """
    enc = _encode_face(face_landmarks)
    if enc is None:
        return None
    if not _registry:
        return None
    by_name: dict[str, list[float]] = {}
    for entry in _registry:
        d = _distance(enc, entry["encoding"])
        by_name.setdefault(entry["name"], []).append(d)

    best_name = None
    best_score = float("inf")
    for name, ds in by_name.items():
        ds.sort()
        # média dos 3 melhores para reduzir ruído
        k = min(3, len(ds))
        score = sum(ds[:k]) / k
        if score < best_score:
            best_score = score
            best_name = name

    if best_score <= threshold:
        return best_name
    return None
