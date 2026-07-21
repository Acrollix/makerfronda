from pathlib import Path

from PIL import Image

from PIL import ImageFont

from fronda.paths import resource_path
from fronda.rendering import _cover_fit, _wrap, safe_filename, save_png_atomic
from fronda.template import Rect


def test_cover_fit_fills_target() -> None:
    result = _cover_fit(Image.new("RGB", (400, 100), "red"), Rect(0, 0, 120, 240))
    assert result.size == (120, 240)


def test_windows_safe_filename() -> None:
    assert safe_filename('a<>:"/\\|?*b') == "a_________b"
    assert safe_filename("CON") == "FRONDA"


def test_atomic_png(tmp_path: Path) -> None:
    output = save_png_atomic(Image.new("RGBA", (3, 2), "red"), tmp_path / "result.png")
    assert output.is_file()
    assert Image.open(output).size == (3, 2)


def test_title_does_not_wrap_without_explicit_newline() -> None:
    font = ImageFont.truetype(str(resource_path("fonts", "BRAVORG.otf")), 42)
    assert _wrap("первая строка вторая", font, 80, 3) is None


def test_title_preserves_explicit_newline() -> None:
    font = ImageFont.truetype(str(resource_path("fonts", "BRAVORG.otf")), 32)
    assert _wrap("первая строка\nвторая строка", font, 400, 3) == ["первая строка", "вторая строка"]
