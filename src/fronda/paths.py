from __future__ import annotations

from pathlib import Path
import sys


def application_dir() -> Path:
    """Directory containing bundled immutable assets."""
    # PyInstaller sets _MEIPASS to its contents directory.  With
    # --contents-directory Data this is exactly `<launcher>/Data`; deriving
    # it from __file__ is unreliable because Python modules live in the
    # embedded archive.
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    module_path = Path(__file__).resolve()
    # In the portable PyInstaller build, modules and assets live together in
    # `Data`; in source mode assets are two levels above this module.
    portable_data = module_path.parents[1]
    if (portable_data / "resources").is_dir() and (portable_data / "qml").is_dir():
        return portable_data
    return module_path.parents[2]


def resource_path(*parts: str) -> Path:
    return application_dir().joinpath("resources", *parts)


def built_in_template_path() -> Path:
    """The FRONDA template shipped with every portable build."""
    return resource_path("templates", "Prevyu.psd")


def app_data_dir() -> Path:
    root = Path.home() / "AppData" / "Local" / "FRONDA" / "CoverMaker"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_export_dir() -> Path:
    """Portable output folder next to the launcher, not inside Data."""
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else application_dir()
    path = root / "Готово"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
