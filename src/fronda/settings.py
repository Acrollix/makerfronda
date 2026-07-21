from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .paths import app_data_dir


@dataclass
class Settings:
    template_path: str = ""
    template_mode: str = "Builtin"
    export_path: str = ""
    display_profiles: dict[str, str] = field(default_factory=dict)
    reduce_motion: bool = False
    overwrite_existing: bool = False
    release_type: str = "Episode"
    artwork_mode: str = "PerEpisode"
    last_window: dict[str, int] = field(default_factory=dict)


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> Settings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {item.name for item in fields(Settings)}
            return Settings(**{key: value for key, value in payload.items() if key in allowed})
        except (OSError, json.JSONDecodeError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
