from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image
import numpy as np
from psd_tools import PSDImage

from .paths import cache_dir


class TemplateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class TemplateProfile:
    layout_revision: int
    fingerprint: str
    source_path: str
    canvas_width: int
    canvas_height: int
    image_layer: str
    overlay_layer: str
    title_layer: str
    episode_layer: str
    base_layer: str
    image_rect: Rect
    title_rect: Rect
    episode_rect: Rect
    episode_plate: Rect
    cover_mask_points: list[list[int]]
    cache_path: str

    def to_dict(self) -> dict[str, Any]:
        # dataclasses.asdict recursively serializes Rect members.
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TemplateProfile":
        for key in ("image_rect", "title_rect", "episode_rect", "episode_plate"):
            payload[key] = Rect(**payload[key])
        return cls(**payload)


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    sidecar = path.with_suffix(".fronda.json")
    if sidecar.is_file():
        digest.update(sidecar.read_bytes())
    return digest.hexdigest()


class TemplateCompiler:
    layout_revision = 4
    required_names = {
        "image": "Фон, картинку сюда",
        "overlay": "Не трогать! Под эту пихать фон картинку.",
        "title": "Название",
        "episode": "Эпизод",
        "base": "Не трогать",
    }

    # Normalised fallback for the supplied FRONDA layout. A designer can put a
    # `<template>.fronda.json` sidecar next to a PSD to override it without a
    # code change: {"cover_mask_points": [[x,y], ...], "episode_plate":
    # [left, top, right, bottom]}. Coordinates are PSD pixels.
    default_cover_mask_1920 = [(842, 107), (1880, 107), (1880, 1004), (1802, 1004), (1802, 1031), (675, 1004), (675, 869), (920, 869), (920, 710), (506, 710), (506, 460)]
    default_episode_plate_1920 = (75, 900, 655, 1033)
    # Canonical FRONDA paragraph frame. It deliberately does not inherit a
    # designer's transient TypeLayer position, so exports match across PCs.
    default_title_frame_1920 = (120, 724, 908, 882)

    @staticmethod
    def _rect(layer: Any) -> Rect:
        left, top, right, bottom = layer.bbox
        return Rect(int(left), int(top), int(right), int(bottom))

    @staticmethod
    def _find(psd: PSDImage, name: str) -> Any:
        normal = name.strip()
        # Permit a designer to organise the required layers into groups
        # without making the template appear invalid to the application.
        for layer in psd.descendants():
            if layer.name.strip() == normal:
                return layer
        raise TemplateError(f"Не найден обязательный слой «{name}».")

    def _layout_geometry(self, source: Path, width: int, height: int) -> tuple[list[list[int]], Rect, Rect]:
        scale_x, scale_y = width / 1920, height / 1080
        points = [[round(x * scale_x), round(y * scale_y)] for x, y in self.default_cover_mask_1920]
        plate_values = self.default_episode_plate_1920
        plate = Rect(round(plate_values[0] * scale_x), round(plate_values[1] * scale_y), round(plate_values[2] * scale_x), round(plate_values[3] * scale_y))
        title_values = self.default_title_frame_1920
        title_frame = Rect(round(title_values[0] * scale_x), round(title_values[1] * scale_y), round(title_values[2] * scale_x), round(title_values[3] * scale_y))
        sidecar = source.with_suffix(".fronda.json")
        if not sidecar.is_file():
            return points, plate, title_frame
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            supplied_points = payload.get("cover_mask_points", points)
            supplied_plate = payload.get("episode_plate", [plate.left, plate.top, plate.right, plate.bottom])
            supplied_title = payload.get("title_frame", [title_frame.left, title_frame.top, title_frame.right, title_frame.bottom])
            if not isinstance(supplied_points, list) or len(supplied_points) < 3 or not isinstance(supplied_plate, list) or len(supplied_plate) != 4 or not isinstance(supplied_title, list) or len(supplied_title) != 4:
                raise ValueError("неверная структура")
            checked_points = [[int(point[0]), int(point[1])] for point in supplied_points]
            checked_plate = Rect(*map(int, supplied_plate))
            checked_title = Rect(*map(int, supplied_title))
            if checked_plate.width <= 0 or checked_plate.height <= 0 or checked_title.width <= 0 or checked_title.height <= 0:
                raise ValueError("пустая геометрия")
            return checked_points, checked_plate, checked_title
        except (OSError, ValueError, TypeError, json.JSONDecodeError, IndexError) as exc:
            raise TemplateError(f"Некорректный файл геометрии {sidecar.name}: {exc}") from exc

    def compile(self, source_path: str | Path) -> TemplateProfile:
        source = Path(source_path)
        if not source.is_file():
            raise TemplateError("PSD-шаблон не найден.")
        try:
            psd = PSDImage.open(source)
        except Exception as exc:  # psd-tools exposes several low-level errors
            raise TemplateError(f"Не удалось открыть PSD: {exc}") from exc
        if psd.color_mode.name != "RGB" or psd.depth != 8:
            raise TemplateError("Поддерживаются только RGB PSD с глубиной 8 бит.")
        layers = {key: self._find(psd, value) for key, value in self.required_names.items()}
        if layers["title"].kind != "type" or layers["episode"].kind != "type":
            raise TemplateError("Слои названия и эпизода должны быть текстовыми.")
        fingerprint = file_fingerprint(source)
        cover_mask_points, episode_plate, title_frame = self._layout_geometry(source, psd.width, psd.height)
        destination = cache_dir() / fingerprint
        destination.mkdir(parents=True, exist_ok=True)
        profile = TemplateProfile(
            fingerprint=fingerprint,
            source_path=str(source),
            canvas_width=psd.width,
            canvas_height=psd.height,
            image_layer=layers["image"].name,
            overlay_layer=layers["overlay"].name,
            title_layer=layers["title"].name,
            episode_layer=layers["episode"].name,
            base_layer=layers["base"].name,
            image_rect=self._rect(layers["image"]),
            title_rect=title_frame,
            episode_rect=self._rect(layers["episode"]),
            episode_plate=episode_plate,
            cover_mask_points=cover_mask_points,
            cache_path=str(destination),
            layout_revision=self.layout_revision,
        )
        # psd-tools composites the nested smart object much more faithfully at
        # document level than at an isolated-layer level. Hide the dynamic
        # texts, then cache the resulting static master plate.
        original_visibility = {layer: layer.visible for layer in (layers["image"], layers["title"], layers["episode"])}
        try:
            for layer in original_visibility:
                layer.visible = False
            static = psd.composite(force=True).convert("RGBA")
        finally:
            for layer, visible in original_visibility.items():
                layer.visible = visible
        static.save(destination / "static.png")
        # Restore only dark/red ornamental lines above the cover. This keeps
        # the cover inside the template while preserving its frame.
        pixels = np.asarray(static)
        red_or_dark = ((pixels[..., 0] < 72) & (pixels[..., 1] < 72) & (pixels[..., 2] < 72)) | ((pixels[..., 0] > 170) & (pixels[..., 1] < 90) & (pixels[..., 2] < 90))
        mask = (pixels[..., 3] > 0) & red_or_dark
        edge_pixels = np.zeros_like(pixels)
        edge_pixels[mask] = pixels[mask]
        edge = Image.fromarray(edge_pixels, "RGBA")
        edge.save(destination / "edge.png")
        (destination / "profile.json").write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    def load(self, source_path: str | Path) -> TemplateProfile | None:
        source = Path(source_path)
        if not source.is_file():
            return None
        fingerprint = file_fingerprint(source)
        profile_path = cache_dir() / fingerprint / "profile.json"
        try:
            profile = TemplateProfile.from_dict(json.loads(profile_path.read_text(encoding="utf-8")))
            root = Path(profile.cache_path)
            if profile.layout_revision != self.layout_revision or not (root / "static.png").is_file() or not (root / "edge.png").is_file():
                return None
            return profile
        except (OSError, json.JSONDecodeError, TypeError, KeyError):
            return None
