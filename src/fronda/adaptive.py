from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any


class DisplayProfile(StrEnum):
    AUTO = "Auto"
    MONITOR = "Monitor"
    TELEVISION = "Television"
    COMPACT_WINDOW = "CompactWindow"


class LayoutMode(StrEnum):
    COMPACT = "Compact"
    MEDIUM = "Medium"
    EXPANDED = "Expanded"
    WIDE = "Wide"


class HeightMode(StrEnum):
    LOW = "Low"
    NORMAL = "Normal"
    TALL = "Tall"


@dataclass(frozen=True)
class ViewportMetrics:
    window_width: float
    window_height: float
    available_width: float
    available_height: float
    dpr: float = 1.0
    physical_diagonal_inches: float | None = None
    maximized: bool = False
    fullscreen: bool = False


@dataclass(frozen=True)
class AdaptiveState:
    effective_profile: DisplayProfile
    layout_mode: LayoutMode
    height_mode: HeightMode
    safe_margin: float
    ui_scale: float
    base_spacing: float
    touch_target: float

    def to_dict(self) -> dict[str, Any]:
        return {key: str(value) if isinstance(value, StrEnum) else value for key, value in asdict(self).items()}


def screen_identifier(name: str, manufacturer: str = "", model: str = "", serial: str = "") -> str:
    source = "|".join((name, manufacturer, model, serial)).encode("utf-8")
    return sha256(source).hexdigest()[:20]


def choose_profile(metrics: ViewportMetrics, selected: DisplayProfile) -> DisplayProfile:
    if selected is not DisplayProfile.AUTO:
        return selected
    if not metrics.maximized and not metrics.fullscreen and (
        metrics.window_width < 1100 or metrics.window_height < 720
    ):
        return DisplayProfile.COMPACT_WINDOW
    if (metrics.maximized or metrics.fullscreen) and (metrics.physical_diagonal_inches or 0) >= 32:
        return DisplayProfile.TELEVISION
    return DisplayProfile.MONITOR


def calculate_layout(metrics: ViewportMetrics, selected: DisplayProfile = DisplayProfile.AUTO) -> AdaptiveState:
    profile = choose_profile(metrics, selected)
    width = metrics.available_width
    if width < 720:
        layout = LayoutMode.COMPACT
    elif width < 1100:
        layout = LayoutMode.MEDIUM
    elif width < 1600:
        layout = LayoutMode.EXPANDED
    else:
        layout = LayoutMode.WIDE
    height = HeightMode.LOW if metrics.available_height < 720 else HeightMode.NORMAL if metrics.available_height < 1000 else HeightMode.TALL
    is_tv = profile is DisplayProfile.TELEVISION
    return AdaptiveState(
        effective_profile=profile,
        layout_mode=layout,
        height_mode=height,
        safe_margin=min(96.0, max(32.0, width * 0.04)) if is_tv else 20.0,
        ui_scale=1.18 if is_tv else 0.92 if profile is DisplayProfile.COMPACT_WINDOW else 1.0,
        base_spacing=18.0 if is_tv else 12.0 if profile is DisplayProfile.COMPACT_WINDOW else 14.0,
        touch_target=52.0 if is_tv else 40.0,
    )
