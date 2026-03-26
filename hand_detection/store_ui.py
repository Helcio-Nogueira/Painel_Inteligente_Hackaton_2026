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

try:
    _FONT_EMOJI = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 36)
    _FONT_EMOJI_SM = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 24)
except OSError:
    _FONT_EMOJI = _FONT_TITLE
    _FONT_EMOJI_SM = _FONT_SUB

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


def _gradient_bg_diagonal(img: Image.Image,
                          tl: tuple[int, int, int],
                          br: tuple[int, int, int]) -> None:
    """Gradiente diagonal (canto sup-esq → canto inf-dir) via numpy (rápido)."""
    w, h = img.size
    xs = np.linspace(0, 1, w, dtype=np.float32)
    ys = np.linspace(0, 1, h, dtype=np.float32)
    t = (ys[:, None] + xs[None, :]) / 2.0
    tl_arr = np.array(tl, dtype=np.float32)
    br_arr = np.array(br, dtype=np.float32)
    pixels = tl_arr + (br_arr - tl_arr) * t[:, :, None]
    img.paste(Image.fromarray(pixels.astype(np.uint8), "RGB"))


def _round_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


_LOGO_IMG: Image.Image | None = None


def _load_logo() -> Image.Image | None:
    global _LOGO_IMG
    if _LOGO_IMG is not None:
        return _LOGO_IMG
    import os
    logo_path = os.path.join(os.path.dirname(__file__), "logo_capvivo.png")
    if not os.path.isfile(logo_path):
        return None
    try:
        logo = Image.open(logo_path).convert("RGBA")
        target_h = 80
        ratio = target_h / logo.height
        target_w = int(logo.width * ratio)
        _LOGO_IMG = logo.resize((target_w, target_h), Image.LANCZOS)
        return _LOGO_IMG
    except Exception:
        return None


def _draw_logo(img: Image.Image, x: int, y: int) -> None:
    """Cola o PNG do logo Capgemini | vivo no canto superior esquerdo."""
    logo = _load_logo()
    if logo is None:
        return
    img.paste(logo, (x, y), logo)


def _draw_emoji_pair(draw: ImageDraw.ImageDraw, x: int, y: int,
                     section_emoji: str, gesture_emoji: str) -> None:
    """Desenha emoji da seção (grande) + emoji do gesto (menor, ao lado)."""
    draw.text((x, y - 6), section_emoji, font=_FONT_EMOJI, fill=(255, 255, 255),
              embedded_color=True)
    draw.text((x + 44, y + 4), gesture_emoji, font=_FONT_EMOJI_SM, fill=(255, 255, 255),
              embedded_color=True)


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
    _gradient_bg_diagonal(img, (18, 22, 72), (88, 28, 108))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(0, width + 140, 160):
        od.ellipse((i - 70, height // 2, i + 90, height + 120), fill=(120, 80, 200, 18))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    margin = 28
    _draw_logo(img, margin, 6)
    draw = ImageDraw.Draw(img)

    if screen is Screen.MENU:
        if greeting_name:
            draw.text((margin, 72), f"Olá {greeting_name}!", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text(
            (margin, 72 if not greeting_name else 128),
            "O que gostaria de fazer hoje?",
            font=_FONT_SUB,
            fill=(210, 210, 240),
        )

        cards = [
            ("🛍️", "👍", "Produtos novos", "Polegar para cima"),
            ("🛒", "✌️", "Meu carrinho", "Sinal de paz (2 dedos)"),
            ("📰", "🖐️", "Notícias do dia", "Palma aberta"),
            ("🙋", "👆", "Chamar atendente", "Aponte o indicador"),
        ]
        y0 = 188
        gap = 14
        card_h = 102
        for sec_emoji, gest_emoji, title, hint in cards:
            _round_rect(
                draw,
                (margin, y0, width - margin, y0 + card_h),
                22,
                fill=(38, 38, 78),
                outline=(100, 160, 220),
                width=2,
            )
            _draw_emoji_pair(draw, margin + 14, y0 + 28, sec_emoji, gest_emoji)
            draw.text((margin + 88, y0 + 22), title, font=_FONT_SUB, fill=(255, 255, 255))
            draw.text((margin + 88, y0 + 58), hint, font=_FONT_SMALL, fill=(180, 190, 220))
            y0 += card_h + gap

        _menu_hint_voltar(draw, margin, width, y0 + 12, height)

        _round_rect(
            draw,
            (margin, height - 100, width - margin, height - 14),
            16,
            fill=(25, 25, 50),
            outline=(100, 160, 220),
            width=1,
        )
        draw.text(
            (margin + 14, height - 82),
            "Dica: use a janela da câmera ao lado para ver sua mão.",
            font=_FONT_SMALL,
            fill=(180, 190, 220),
        )

    elif screen is Screen.NOVIDADES:
        draw.text((margin, 72), "Novidades", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text((margin, 130), "Destaques fresquinhos pra você", font=_FONT_SUB, fill=(180, 200, 240))
        draw.text(
            (margin, 156),
            "Olhe o produto + OK ou faça o número com a mão",
            font=_FONT_SMALL,
            fill=(160, 180, 220),
        )
        in_cart = set(cart_product_ids or [])
        y = NOVIDADES_Y0
        for idx, (pid, em, name, sub) in enumerate(NOVIDADES_PRODUCTS):
            if y + NOVIDADES_ROW_H > height - BACK_ZONE_H - 8:
                break
            hover = novidades_hover_id == pid
            added = pid in in_cart
            fill_c = (50, 50, 95) if hover else (38, 38, 78)
            if added:
                fill_c = (30, 70, 55) if hover else (25, 60, 48)
            outline_c = (140, 200, 255) if hover else (100, 160, 220)
            if added:
                outline_c = (100, 220, 150) if hover else (80, 180, 120)
            ow = 3 if hover else 2
            _round_rect(draw, (margin, y, width - margin, y + NOVIDADES_ROW_H), 18, fill_c, outline_c, ow)
            num_label = f"{idx + 1}."
            draw.text((margin + 14, y + 28), num_label, font=_FONT_SUB, fill=(140, 200, 255))
            if added:
                draw.text(
                    (margin + 48, y + 28),
                    "Adicionado ao carrinho!",
                    font=_FONT_SUB,
                    fill=(160, 240, 190),
                )
            else:
                draw.text((margin + 48, y + 18), name, font=_FONT_SUB, fill=(255, 255, 255))
                draw.text((margin + 48, y + 52), sub, font=_FONT_SMALL, fill=(160, 180, 220))
            y += NOVIDADES_ROW_GAP
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.CARRINHO:
        draw.text((margin, 72), "Seu carrinho", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text(
            (margin, 128),
            "Olhe o item + OK para remover",
            font=_FONT_SMALL,
            fill=(160, 180, 220),
        )
        c_ids = list(cart_product_ids or [])
        if not c_ids:
            _round_rect(
                draw,
                (margin, 168, width - margin, height - BACK_ZONE_H - 24),
                24,
                (38, 38, 78),
                (100, 160, 220),
                2,
            )
            draw.text((margin + 24, 228), "Tudo tranquilo por aqui!", font=_FONT_SUB, fill=(255, 255, 255))
            draw.text(
                (margin + 24, 264),
                "Em Novidades, selecione produtos com a mão",
                font=_FONT_BODY,
                fill=(180, 200, 240),
            )
            draw.text(
                (margin + 24, 290),
                "ou olhe + OK para adicionar ao carrinho.",
                font=_FONT_BODY,
                fill=(180, 200, 240),
            )
        else:
            y = CARRINHO_LIST_Y0
            for pid in c_ids:
                if y + CARRINHO_ROW_H > height - BACK_ZONE_H - 24:
                    break
                row = product_row(pid)
                em, name, sub = ("", product_label(pid), "") if row is None else (row[1], row[2], row[3])
                hover = carrinho_hover_id == pid
                fill_c = (50, 50, 95) if hover else (38, 38, 78)
                outline_c = (140, 200, 255) if hover else (100, 160, 220)
                ow = 3 if hover else 2
                _round_rect(draw, (margin, y, width - margin, y + CARRINHO_ROW_H), 16, fill_c, outline_c, ow)
                draw.text((margin + 16, y + 12), name, font=_FONT_SUB, fill=(255, 255, 255))
                if sub:
                    draw.text((margin + 16, y + 34), sub, font=_FONT_SMALL, fill=(160, 180, 220))
                y += CARRINHO_ROW_H + CARRINHO_ROW_GAP
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.NOTICIAS:
        draw.text((margin, 72), "Notícias do dia", font=_FONT_TITLE, fill=(255, 248, 240))
        news = [
            "Tech: IA generativa acelera protótipos em hackathons.",
            "Lifestyle: cafeterias com desconto para quem usa transporte verde.",
            "Curiosidade: lojas físicas misturam gestos e telas interativas.",
        ]
        y = 152
        for line in news:
            if y + 76 > height - BACK_ZONE_H - 8:
                break
            _round_rect(draw, (margin, y, width - margin, y + 72), 16, (38, 38, 78), (100, 160, 220), 2)
            draw.text((margin + 18, y + 22), line, font=_FONT_SMALL, fill=(220, 225, 240))
            y += 84
        _draw_barra_voltar(draw, margin, width, height)

    elif screen is Screen.REGISTRAR:
        draw.text((margin, 72), "Chamar atendente", font=_FONT_TITLE, fill=(255, 248, 240))
        draw.text(
            (margin, 160),
            "Aguarde um momento,",
            font=_FONT_SUB,
            fill=(255, 230, 180),
        )
        draw.text(
            (margin, 190),
            "o atendente já está chegando.",
            font=_FONT_SUB,
            fill=(255, 230, 180),
        )
        draw.text((margin, 250), "✊", font=_FONT_EMOJI, fill=(255, 255, 255),
                  embedded_color=True)
        draw.text((margin + 48, 254), "Punho fechado para cancelar", font=_FONT_SMALL,
                  fill=(180, 190, 220))
        _draw_barra_voltar(draw, margin, width, height)

    if gesture_label:
        pill_w = min(width - 2 * margin, 360)
        _round_rect(
            draw,
            (width - margin - pill_w, 16, width - margin, 54),
            16,
            fill=(25, 30, 55),
            outline=(80, 200, 160),
            width=1,
        )
        draw.text(
            (width - margin - pill_w + 12, 26),
            gesture_label[:52],
            font=_FONT_SMALL,
            fill=(140, 230, 190),
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
    _round_rect(draw, box, 18, (30, 30, 60), (100, 160, 220), 2)
    draw.text((margin + 16, top + 12), "Voltar à tela anterior", font=_FONT_SUB, fill=(200, 210, 240))
    draw.text(
        (margin + 16, top + 40),
        "Nas telas internas: punho fechado (~0,5 s) volta ao menu.",
        font=_FONT_SMALL,
        fill=(160, 180, 220),
    )


def _draw_barra_voltar(draw: ImageDraw.ImageDraw, margin: int, width: int, height: int) -> None:
    """Faixa inferior fixa: gesto obrigatório para voltar (sempre visível nas telas internas)."""
    top = height - BACK_ZONE_H
    _round_rect(
        draw,
        (margin, top, width - margin, height - 10),
        20,
        fill=(28, 28, 55),
        outline=(100, 160, 220),
        width=2,
    )
    draw.text((margin + 14, top + 14), "VOLTAR", font=_FONT_SUB, fill=(180, 200, 240))
    draw.text(
        (margin + 14, top + 46),
        "Feche a mão (punho). Mantenha firme cerca de meio segundo.",
        font=_FONT_BODY,
        fill=(160, 180, 220),
    )
    draw.text(
        (margin + 14, top + 72),
        "Retorna ao menu principal.",
        font=_FONT_SMALL,
        fill=(130, 170, 210),
    )


def cv2_compatible(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img)
    return rgb[:, :, ::-1].copy()
