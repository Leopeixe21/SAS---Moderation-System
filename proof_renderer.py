from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH = 920
PADDING = 28
BG = "#313338"
PANEL = "#2b2d31"
TEXT = "#f2f3f5"
MUTED = "#b5bac1"
LINK = "#00a8fc"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in (text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines[:12]


def _load_images(evidence: Iterable[tuple[str, bytes]]) -> list[Image.Image]:
    images = []
    for _, payload in evidence:
        try:
            with Image.open(io.BytesIO(payload)) as source:
                images.append(ImageOps.exif_transpose(source).convert("RGB"))
        except OSError:
            continue
    return images


def render_message_proof(
    *,
    display_name: str,
    username: str,
    avatar: bytes | None,
    content: str,
    created_at: datetime,
    guild_name: str,
    guild_id: int,
    channel_name: str,
    channel_id: int,
    message_id: int,
    user_id: int,
    evidence: list[tuple[str, bytes]],
) -> bytes:
    """Cria uma captura visual reconstruída a partir do evento recebido do Discord."""
    title_font = _font(22, bold=True)
    body_font = _font(20)
    small_font = _font(15)
    meta_font = _font(16)
    probe = Image.new("RGB", (WIDTH, 200), BG)
    probe_draw = ImageDraw.Draw(probe)
    text_lines = _wrap(probe_draw, content, body_font, WIDTH - 124) if content.strip() else []
    text_height = len(text_lines) * 27

    pictures = _load_images(evidence)
    columns = 1 if len(pictures) == 1 else 2
    cell_width = WIDTH - 124 if columns == 1 else (WIDTH - 136) // 2
    cell_height = 390 if columns == 1 else 285
    rows = (len(pictures) + columns - 1) // columns
    gallery_height = rows * cell_height + max(0, rows - 1) * 8 if pictures else 0
    header_height = 92
    metadata_height = 166
    height = PADDING * 2 + header_height + text_height + (12 if text_lines else 0) + gallery_height + 22 + metadata_height

    canvas = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(canvas)

    avatar_box = (PADDING, PADDING, PADDING + 58, PADDING + 58)
    if avatar:
        try:
            with Image.open(io.BytesIO(avatar)) as source:
                avatar_image = ImageOps.fit(source.convert("RGB"), (58, 58))
            mask = Image.new("L", (58, 58), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 57, 57), fill=255)
            canvas.paste(avatar_image, avatar_box[:2], mask)
        except OSError:
            draw.ellipse(avatar_box, fill="#5865f2")
    else:
        draw.ellipse(avatar_box, fill="#5865f2")

    text_x = PADDING + 74
    draw.text((text_x, PADDING), display_name, font=title_font, fill=TEXT)
    name_width = draw.textbbox((0, 0), display_name, font=title_font)[2]
    timestamp = created_at.astimezone().strftime("%d/%m/%Y %H:%M")
    draw.text((text_x + name_width + 12, PADDING + 5), f"@{username}  •  {timestamp}", font=small_font, fill=MUTED)

    y = PADDING + 42
    for line in text_lines:
        draw.text((text_x, y), line, font=body_font, fill=TEXT)
        y += 27
    if text_lines:
        y += 12

    for index, picture in enumerate(pictures):
        row, column = divmod(index, columns)
        x = text_x + column * (cell_width + 8)
        image_y = y + row * (cell_height + 8)
        fitted = ImageOps.contain(picture, (cell_width, cell_height))
        tile = Image.new("RGB", (cell_width, cell_height), PANEL)
        tile.paste(fitted, ((cell_width - fitted.width) // 2, (cell_height - fitted.height) // 2))
        canvas.paste(tile, (x, image_y))
    y += gallery_height + 22

    panel_box = (text_x, y, WIDTH - PADDING, y + metadata_height)
    draw.rounded_rectangle(panel_box, radius=8, fill=PANEL)
    info_x, info_y = text_x + 18, y + 14
    draw.text((info_x, info_y), f"Mensagem enviada em #{channel_name} • {guild_name}", font=meta_font, fill=LINK)
    details = (
        f"ID do usuário: {user_id}\n"
        f"ID do servidor: {guild_id}\n"
        f"ID do canal: {channel_id}\n"
        f"ID da mensagem: {message_id}"
    )
    draw.multiline_text((info_x, info_y + 30), details, font=small_font, fill=MUTED, spacing=5)
    draw.text((WIDTH - 230, y + metadata_height - 30), "SAS • Registro de moderação", font=small_font, fill=MUTED)

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
