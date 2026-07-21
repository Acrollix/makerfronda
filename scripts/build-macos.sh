#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv-macos"
RELEASE="$ROOT/release-macos"
APP_NAME="FRONDA Cover Maker"

rm -rf "$VENV" "$RELEASE"
"$PYTHON" -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install --upgrade pip
python -m pip install . pyinstaller

# macOS requires ICNS rather than the Windows ICO container.
python - <<'PY'
from pathlib import Path
from PIL import Image
source = Path("resources/images/fronda.ico")
target = Path("resources/images/fronda.icns")
image = Image.open(source).convert("RGBA")
image.save(target, format="ICNS", sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
PY

python -m PyInstaller \
  --noconfirm --clean --windowed \
  --target-architecture arm64 \
  --osx-bundle-identifier ru.fronda.covermaker \
  --icon "$ROOT/resources/images/fronda.icns" \
  --name "$APP_NAME" \
  --paths "$ROOT/src" \
  --add-data "$ROOT/qml:qml" \
  --add-data "$ROOT/resources:resources" \
  --distpath "$RELEASE" \
  --workpath "$ROOT/build-macos" \
  --specpath "$ROOT/build-macos" \
  "$ROOT/src/fronda/main.py"

mkdir -p "$ROOT/release"
ditto -c -k --sequesterRsrc --keepParent \
  "$RELEASE/$APP_NAME.app" \
  "$ROOT/release/FRONDA-Cover-Maker-macOS-ARM64.zip"
