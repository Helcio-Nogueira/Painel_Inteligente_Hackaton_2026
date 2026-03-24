"""Interface visual da 'loja' (segunda janela), renderizada com Pillow."""

from __future__ import annotations

from enum import Enum

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class Screen(Enum):
    MENU = 1
    NOVIDADES = 2
    CARRINHO = 3
    NOTICIAS = 4
    REGISTRAR = 5  # Registrar rosto (gesto indicador)


def _load_fonts():
    candidates = [
        ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf"),
        ("C:/Windows/Fonts/seguiemj.ttf", "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for bold_path, reg_path in candidates:
        try:
            return (
                ImageFont.truetype(bold_path, 38),
                ImageFont.truetype(reg_path, 22),
                ImageFont.truetype(reg_path, 18),
                ImageFont.truetype(reg_path, 15),
            )
        except OSError:
            continue
    d = ImageFont.load_default()
    return d, d, d, d


_FONT_TITLE, _FONT_SUB, _FONT_BODY, _FONT_SMALL = _load_fonts()

# Altura reservada para a barra “como voltar” (telas internas).
BACK_ZONE_H = 128

# Produtos em Novidades (id estável para carrinho / hit-test)
NOVIDADES_MARGIN = 28
NOVIDADES_Y0 = 188
NOVIDADES_ROW_H = 86
NOVIDADES_ROW_GAP = 98

NOVIDADES_PRODUCTS: list[tuple[str, str, str, str]] = [
    ("aura", "🎧", "Fones Aura Pro", "Novo · Som espacial"),
    ("fitneo", "⌚", "Pulseira Fit Neo", "Lançamento · 7 dias bateria"),
    ("caneca", "☕", "Caneca térmica Glow", "Edição limitada"),
    ("lamp", "💡", "Lâmpada smart Aura", "RGB · voz e app"),
]


def novidades_product_regions(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Retorna (id_produto, (x1, y1, x2, y2)) em pixels, alinhado ao desenho da tela Novidades."""
    margin = NOVIDADES_MARGIN
    out: list[tuple[str, tuple[int, int, int, int]]] = []
    y = NOVIDADES_Y0
    for pid, _em, _n, _s in NOVIDADES_PRODUCTS:
        if y + NOVIDADES_ROW_H > height - BACK_ZONE_H - 8:
            break
        out.append((pid, (margin, y, width - margin, y + NOVIDADES_ROW_H)))
        y += NOVIDADES_ROW_GAP
    return out


def resolve_novidades_hover(
    gaze_xy: tuple[int, int] | None,
    width: int,
    height: int,
) -> str | None:
    """
    Produto sob o olhar: hit-test com margem + fallback por faixa vertical
    (o gaze costuma ser impreciso; sem isso a pinça não adiciona ao carrinho).
    """
    if gaze_xy is None:
        return None
    gx, gy = gaze_xy
    regions = novidades_product_regions(width, height)
    if not regions:
        return None
    pad_x = 28
    pad_y = 22
    for pid, (x1, y1, x2, y2) in regions:
        if x1 - pad_x <= gx <= x2 + pad_x and y1 - pad_y <= gy <= y2 + pad_y:
            return pid
    for pid, (x1, y1, x2, y2) in regions:
        if y1 <= gy <= y2 and x1 - 8 <= gx <= x2 + 8:
            return pid
    best_id: str | None = None
    best_d = 1e9
    for pid, (x1, y1, x2, y2) in regions:
        cy = (y1 + y2) // 2
        cx = (x1 + x2) // 2
        d = abs(gy - cy) + abs(gx - cx) * 0.35
        if d < best_d:
            best_d = d
            best_id = pid
    if best_id is not None and best_d < max(110, NOVIDADES_ROW_GAP):
        return best_id
    return None


# Lista do carrinho: mesma largura que a caixa principal; alinhado ao desenho em render_store.
CARRINHO_LIST_Y0 = 176
CARRINHO_ROW_H = 54
CARRINHO_ROW_GAP = 12


def carrinho_item_regions(
    width: int, height: int, cart_product_ids: list[str]
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """(product_id, box) para cada linha do carrinho (hit-test gaze + pinça)."""
    margin = NOVIDADES_MARGIN
    out: list[tuple[str, tuple[int, int, int, int]]] = []
    y = CARRINHO_LIST_Y0
    for pid in cart_product_ids:
        if y + CARRINHO_ROW_H > height - BACK_ZONE_H - 24:
            break
        out.append((pid, (margin, y, width - margin, y + CARRINHO_ROW_H)))
        y += CARRINHO_ROW_H + CARRINHO_ROW_GAP
    return out


def resolve_carrinho_hover(
    gaze_xy: tuple[int, int] | None,
    width: int,
    height: int,
    cart_product_ids: list[str],
) -> str | None:
    """Qual item do carrinho está sob o olhar (com margens, como em Novidades)."""
    if gaze_xy is None or not cart_product_ids:
        return None
    gx, gy = gaze_xy
    regions = carrinho_item_regions(width, height, cart_product_ids)
    if not regions:
        return None
    pad_x = 28
    pad_y = 20
    for pid, (x1, y1, x2, y2) in regions:
        if x1 - pad_x <= gx <= x2 + pad_x and y1 - pad_y <= gy <= y2 + pad_y:
            return pid
    for pid, (x1, y1, x2, y2) in regions:
        if y1 <= gy <= y2 and x1 - 8 <= gx <= x2 + 8:
            return pid
    best_id: str | None = None
    best_d = 1e9
    for pid, (x1, y1, x2, y2) in regions:
        cy = (y1 + y2) // 2
        cx = (x1 + x2) // 2
        d = abs(gy - cy) + abs(gx - cx) * 0.35
        if d < best_d:
            best_d = d
            best_id = pid
    if best_id is not None and best_d < max(100, CARRINHO_ROW_GAP + CARRINHO_ROW_H):
        return best_id
    return None


def product_label(product_id: str) -> str:
    for pid, _em, name, _sub in NOVIDADES_PRODUCTS:
        if pid == product_id:
            return name
    return product_id


def product_row(product_id: str) -> tuple[str, str, str, str] | None:
    for row in NOVIDADES_PRODUCTS:
        if row[0] == product_id:
            return row
    return None


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _gradient_bg(img: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    px = img.load()
    w, h = img.size
    for y in range(h):
        t = y / max(h - 1, 1)
        c = _lerp_color(top, bottom, t)
        for x in range(w):
            px[x, y] = c


def _round_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render_store(
    width: int,
    height: int,
    screen: Screen,
    gesture_label: str | None = None,
    gaze_xy: tuple[int, int] | None = None,
    greeting_name: str | None = None,
    register_countdown: float | None = None,
    register_feedback: str | None = None,
    novidades_hover_id: str | None = None,
    cart_product_ids: list[str] | None = None,
    carrinho_hover_id: str | None = None,
) -> np.ndarray:
    img = Image.new("RGB", (width, height))
    _gradient_bg(img, (45, 27, 78), (18, 58, 92))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(0, width + 120, 140):
        od.ellipse((i - 60, height // 3, i + 80, height + 100), fill=(255, 200, 120, 25))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    margin = 28

    if screen is Screen.MENU:
        if greeting_name:
            draw.text((margin, 72), f"Olá {greeting_name}!", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text(
            (margin, 72 if not greeting_name else 128),
            "O que gostaria de fazer hoje?",
            font=_FONT_SUB,
            fill=(230, 220, 255),
        )

        cards = [
            ("🆕", "Produtos novos", "Polegar bem para cima (fora do punho)"),
            ("✌️", "Meu carrinho", "Faça o sinal de paz (2 dedos)"),
            ("🖐️", "Notícias do dia", "Abra a palma da mão"),
            ("👆", "Registrar meu rosto", "Aponte só o indicador"),
        ]
        y0 = 188
        gap = 14
        card_h = 102
        for emoji, title, hint in cards:
            _round_rect(
                draw,
                (margin, y0, width - margin, y0 + card_h),
                22,
                fill=(88, 72, 118),
                outline=(210, 185, 255),
                width=2,
            )
            draw.text((margin + 20, y0 + 18), emoji, font=_FONT_TITLE, fill=(255, 255, 255))
            draw.text((margin + 88, y0 + 22), title, font=_FONT_SUB, fill=(255, 255, 255))
            draw.text((margin + 88, y0 + 58), hint, font=_FONT_SMALL, fill=(220, 210, 245))
            y0 += card_h + gap

        _menu_hint_voltar(draw, margin, width, y0 + 12, height)

        _round_rect(
            draw,
            (margin, height - 100, width - margin, height - 14),
            16,
            fill=(32, 28, 52),
            outline=(255, 195, 130),
            width=1,
        )
        draw.text(
            (margin + 14, height - 82),
            "Dica: use a janela da câmera ao lado para ver sua mão.",
            font=_FONT_SMALL,
            fill=(255, 230, 200),
        )

    elif screen is Screen.NOVIDADES:
        draw.text((margin, 72), "✨ Novidades", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text((margin, 130), "Destaques fresquinhos pra você", font=_FONT_SUB, fill=(200, 230, 255))
        draw.text(
            (margin, 156),
            "Olhe o produto + 👌 A-OK — cada item só entra uma vez no carrinho",
            font=_FONT_SMALL,
            fill=(255, 230, 200),
        )
        in_cart = set(cart_product_ids or [])
        y = NOVIDADES_Y0
        for pid, em, name, sub in NOVIDADES_PRODUCTS:
            if y + NOVIDADES_ROW_H > height - BACK_ZONE_H - 8:
                break
            hover = novidades_hover_id == pid
            added = pid in in_cart
            fill = (100, 85, 140) if hover else (82, 70, 118)
            if added:
                fill = (55, 95, 75) if hover else (48, 82, 68)
            outline = (255, 220, 120) if hover else (200, 195, 240)
            if added:
                outline = (140, 255, 170) if hover else (100, 200, 130)
            ow = 3 if hover else 2
            _round_rect(draw, (margin, y, width - margin, y + NOVIDADES_ROW_H), 18, fill, outline, ow)
            if added:
                draw.text(
                    (margin + 20, y + 28),
                    "Adicionado ao carrinho!",
                    font=_FONT_SUB,
                    fill=(200, 255, 215),
                )
            else:
                draw.text((margin + 16, y + 20), em, font=_FONT_TITLE, fill=(255, 255, 255))
                draw.text((margin + 72, y + 18), name, font=_FONT_SUB, fill=(255, 255, 255))
                draw.text((margin + 72, y + 52), sub, font=_FONT_SMALL, fill=(210, 220, 255))
            y += NOVIDADES_ROW_GAP
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.CARRINHO:
        draw.text((margin, 72), "🛒 Seu carrinho", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text(
            (margin, 128),
            "Olhe o item + 👌 A-OK para remover do carrinho",
            font=_FONT_SMALL,
            fill=(255, 230, 200),
        )
        c_ids = list(cart_product_ids or [])
        if not c_ids:
            _round_rect(
                draw,
                (margin, 168, width - margin, height - BACK_ZONE_H - 24),
                24,
                (58, 72, 98),
                (110, 210, 170),
                2,
            )
            draw.text((margin + 24, 228), "Tudo tranquilo por aqui!", font=_FONT_SUB, fill=(255, 255, 255))
            draw.text(
                (margin + 24, 264),
                "Em Novidades, olhe um produto e faça o gesto 👌 A-OK",
                font=_FONT_BODY,
                fill=(220, 235, 255),
            )
            draw.text(
                (margin + 24, 290),
                "para adicionar ao carrinho.",
                font=_FONT_BODY,
                fill=(220, 235, 255),
            )
        else:
            y = CARRINHO_LIST_Y0
            for pid in c_ids:
                if y + CARRINHO_ROW_H > height - BACK_ZONE_H - 24:
                    break
                row = product_row(pid)
                em, name, sub = ("📦", product_label(pid), "") if row is None else (row[1], row[2], row[3])
                hover = carrinho_hover_id == pid
                fill = (88, 105, 135) if hover else (70, 88, 118)
                outline = (255, 200, 120) if hover else (130, 200, 255)
                ow = 3 if hover else 2
                _round_rect(draw, (margin, y, width - margin, y + CARRINHO_ROW_H), 16, fill, outline, ow)
                draw.text((margin + 14, y + 10), em, font=_FONT_TITLE, fill=(255, 255, 255))
                draw.text((margin + 64, y + 8), name, font=_FONT_SUB, fill=(255, 255, 255))
                if sub:
                    draw.text((margin + 64, y + 32), sub, font=_FONT_SMALL, fill=(210, 220, 255))
                y += CARRINHO_ROW_H + CARRINHO_ROW_GAP
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.NOTICIAS:
        draw.text((margin, 72), "📰 Notícias do dia", font=_FONT_TITLE, fill=(255, 248, 240))
        news = [
            "Tech: IA generativa acelera protótipos em hackathons.",
            "Lifestyle: cafeterias com desconto para quem usa transporte verde.",
            "Curiosidade: lojas físicas misturam gestos e telas interativas.",
        ]
        y = 152
        for line in news:
            if y + 76 > height - BACK_ZONE_H - 8:
                break
            _round_rect(draw, (margin, y, width - margin, y + 72), 16, (78, 65, 102), (230, 165, 115), 2)
            draw.text((margin + 18, y + 22), line, font=_FONT_SMALL, fill=(255, 252, 245))
            y += 84
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.REGISTRAR:
        draw.text((margin, 72), "👤 Registrar rosto", font=_FONT_TITLE, fill=(255, 248, 240))
        if register_countdown is not None and register_countdown > 0:
            sec = int(register_countdown) + 1
            draw.text(
                (margin, 140),
                f"Posicione seu rosto na câmera e aguarde... {sec}s",
                font=_FONT_SUB,
                fill=(255, 230, 180),
            )
            if register_feedback:
                draw.text(
                    (margin, 172),
                    f"→ {register_feedback}",
                    font=_FONT_SMALL,
                    fill=(255, 210, 140),
                )
            _round_rect(
                draw,
                (margin, 200, width - margin, 260),
                16,
                fill=(60, 45, 90),
                outline=(200, 150, 255),
                width=2,
            )
            pct = max(0, 1.0 - register_countdown / 5.0)
            bar_w = (width - 2 * margin - 32) * pct
            draw.rectangle(
                (margin + 16, 218, margin + 16 + int(bar_w), 242),
                fill=(150, 100, 255),
            )
        else:
            msg = register_feedback or "Aguardando rosto... Posicione-se na câmera."
            draw.text(
                (margin, 140),
                msg,
                font=_FONT_SUB,
                fill=(255, 230, 180),
            )
        _draw_barra_voltar(draw, margin, width, height)

    if gesture_label:
        pill_w = min(width - 2 * margin, 360)
        _round_rect(
            draw,
            (width - margin - pill_w, 16, width - margin, 54),
            16,
            fill=(25, 35, 55),
            outline=(120, 255, 190),
            width=1,
        )
        draw.text(
            (width - margin - pill_w + 12, 26),
            gesture_label[:52],
            font=_FONT_SMALL,
            fill=(170, 255, 210),
        )

    if gaze_xy is not None:
        gx, gy = gaze_xy
        r = 14
        draw.ellipse(
            (gx - r, gy - r, gx + r, gy + r),
            fill=(255, 80, 60),
            outline=(255, 255, 255),
        )

    return cv2_compatible(img)


def _menu_hint_voltar(
    draw: ImageDraw.ImageDraw,
    margin: int,
    width: int,
    top: int,
    height: int,
) -> None:
    """Lembrete no menu: como voltar quando estiver dentro de uma seção."""
    box = (margin, top, width - margin, top + 72)
    _round_rect(draw, box, 18, (55, 42, 85), (255, 165, 90), 2)
    draw.text((margin + 16, top + 12), "↩ Voltar à tela anterior", font=_FONT_SUB, fill=(255, 230, 200))
    draw.text(
        (margin + 16, top + 40),
        "Dentro de Novidades, Carrinho ou Notícias: use 🔙 punho fechado (~0,5 s) → volta ao menu.",
        font=_FONT_SMALL,
        fill=(235, 220, 255),
    )


def _draw_barra_voltar(draw: ImageDraw.ImageDraw, margin: int, width: int, height: int) -> None:
    """Faixa inferior fixa: gesto obrigatório para voltar (sempre visível nas telas internas)."""
    top = height - BACK_ZONE_H
    _round_rect(
        draw,
        (margin, top, width - margin, height - 10),
        20,
        fill=(42, 28, 58),
        outline=(255, 160, 80),
        width=3,
    )
    draw.text((margin + 14, top + 8), "🔙", font=_FONT_TITLE, fill=(255, 230, 160))
    draw.text((margin + 58, top + 10), "VOLTAR", font=_FONT_SUB, fill=(255, 200, 130))
    draw.text((margin + 168, top + 8), "✊", font=_FONT_TITLE, fill=(255, 255, 255))
    draw.text(
        (margin + 226, top + 12),
        "Gesto para voltar à tela anterior",
        font=_FONT_SUB,
        fill=(255, 248, 240),
    )
    draw.text(
        (margin + 14, top + 46),
        "Feche a mão (punho). Mantenha firme cerca de meio segundo.",
        font=_FONT_BODY,
        fill=(220, 210, 245),
    )
    draw.text(
        (margin + 14, top + 72),
        "→ Retorna ao menu principal (tela anterior neste fluxo).",
        font=_FONT_SMALL,
        fill=(180, 255, 200),
    )


def cv2_compatible(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img)
    return rgb[:, :, ::-1].copy()
