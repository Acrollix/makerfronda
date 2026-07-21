from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from .paths import resource_path
from .template import Rect, TemplateProfile


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderRequest:
    title: str
    episode: int
    image: Image.Image
    title_alignment: str = "left"
    release_type: str = "Episode"


def _cover_fit(source: Image.Image, rect: Rect) -> Image.Image:
    image = ImageOps.exif_transpose(source).convert("RGBA")
    scale = max(rect.width / image.width, rect.height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    image = image.resize(size, Image.Resampling.LANCZOS)
    left, top = (image.width - rect.width) // 2, (image.height - rect.height) // 2
    return image.crop((left, top, left + rect.width, top + rect.height))


def _font(path: Path, size: int, variation: int | None = None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(path), size=size)
    if variation is not None:
        try:
            font.set_variation_by_axes([variation])
        except OSError:
            pass
    return font


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int) -> list[str] | None:
    lines: list[str] = []
    # Newlines are entirely author-controlled. Do not auto-wrap a title: if a
    # line is too wide, the caller reduces its font size until it fits.
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = " ".join(paragraph.split())
        if not line or font.getlength(line) > width:
            return None
        lines.append(line)
    return lines if len(lines) <= max_lines else None


def fit_title(text: str, rect: Rect) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    font_path = resource_path("fonts", "BRAVORG.otf")
    # Start from the actual PSD paragraph-frame height instead of a fixed
    # type size. A short title can therefore occupy the whole frame, while a
    # long title progressively scales down and wraps to two balanced lines.
    largest = min(110, max(32, round(rect.height * 0.92)))
    for size in range(largest, 15, -1):
        font = _font(font_path, size)
        lines = _wrap(text, font, rect.width, max_lines=3)
        if not lines:
            continue
        bbox = font.getbbox("Ag")
        line_height = bbox[3] - bbox[1] + max(2, round(size * 0.10))
        if len(lines) * line_height <= rect.height:
            return font, lines, line_height
    raise RenderError("Название не помещается в область шаблона.")


class CoverRenderer:
    def __init__(self, profile: TemplateProfile) -> None:
        self.profile = profile
        root = Path(profile.cache_path)
        self.static = Image.open(root / "static.png").convert("RGBA")
        self.edge = Image.open(root / "edge.png").convert("RGBA")
        self.cover_mask = self._cover_mask()

    def _cover_mask(self) -> Image.Image:
        """Editable window supplied by the compiled PSD profile."""
        mask = Image.new("L", (self.profile.canvas_width, self.profile.canvas_height), 0)
        ImageDraw.Draw(mask).polygon(self.profile.cover_mask_points, fill=255)
        return mask

    def render(self, request: RenderRequest) -> Image.Image:
        if not request.title.strip():
            raise RenderError("Введите название релиза.")
        canvas = self.static.copy()
        cover = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        cover.alpha_composite(_cover_fit(request.image, self.profile.image_rect), (self.profile.image_rect.left, self.profile.image_rect.top))
        cover.putalpha(ImageChops.multiply(cover.getchannel("A"), self.cover_mask))
        canvas.alpha_composite(cover)
        canvas.alpha_composite(self.edge)
        # The extracted ornament layer contains the solid red episode plate.
        # Text must be painted last or that plate hides it completely.
        self._draw_title(canvas, request.title.strip(), request.title_alignment)
        self._draw_episode(canvas, request.episode, request.release_type)
        return canvas

    def _draw_title(self, canvas: Image.Image, text: str, alignment: str) -> None:
        font, lines, line_height = fit_title(text, self.profile.title_rect)
        draw = ImageDraw.Draw(canvas)
        # Center the *visible glyph block* in the text frame. Pillow's text
        # origin includes a font-specific ascender offset, so using rect.top
        # directly makes the title appear noticeably too low in Photoshop's
        # paragraph box.
        sample_box = draw.textbbox((0, 0), "Ag", font=font)
        glyph_height = sample_box[3] - sample_box[1]
        block_height = glyph_height * len(lines) + max(0, len(lines) - 1) * (line_height - glyph_height)
        # A tiny optical lift matches the baseline placement in the PSD.
        visible_y = self.profile.title_rect.top + max(0, (self.profile.title_rect.height - block_height) // 2) - 4
        for line in lines:
            x = self.profile.title_rect.left
            if alignment == "center":
                x += max(0, (self.profile.title_rect.width - round(font.getlength(line))) // 2)
            draw.text((x, visible_y - sample_box[1]), line, font=font, fill=(0, 0, 0, 255), stroke_width=0)
            visible_y += line_height

    def _draw_episode(self, canvas: Image.Image, episode: int, release_type: str) -> None:
        if episode < 0:
            raise RenderError("Номер серии не может быть отрицательным.")
        # The PSD text bounds only cover the original lettering, not the full
        # red plate. Use the plate geometry so "ЭПИЗОД 1" and "ЭПИЗОД 99" are
        # both optically centred and legible.
        plate = self.profile.episode_plate
        label = "ФИЛЬМ" if release_type == "Film" else f"ЭПИЗОД {episode}"
        font_path = resource_path("fonts", "CASCADIACODE.ttf")
        font = _font(font_path, 108, variation=700)
        while font.getlength(label) > plate.width - 42 and font.size > 42:
            font = _font(font_path, font.size - 2, variation=700)
        draw = ImageDraw.Draw(canvas)
        box = draw.textbbox((0, 0), label, font=font)
        x = plate.left + (plate.width - round(font.getlength(label))) // 2
        y = plate.top + (plate.height - (box[3] - box[1])) // 2 - box[1]
        draw.text((x, y), label, font=font, fill=(255, 255, 255, 255))


def safe_filename(value: str, fallback: str = "FRONDA") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    if not value or value.upper() in {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}:
        return fallback
    return value[:160]


def save_png_atomic(image: Image.Image, destination: Path, overwrite: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        stem, suffix, number = destination.stem, destination.suffix, 2
        while destination.exists():
            destination = destination.with_name(f"{stem} ({number}){suffix}")
            number += 1
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".fronda-", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        image.save(temporary, format="PNG")
        with Image.open(temporary) as check:
            if check.size != image.size or check.format != "PNG":
                raise RenderError("Не удалось проверить созданный PNG.")
        os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
