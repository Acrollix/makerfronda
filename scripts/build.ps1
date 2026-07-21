$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Сначала создайте .venv и установите зависимости.' }

# Portable distribution: the executable and all dependencies stay in one
# folder, without onefile extraction into the temporary directory.
$releaseRoot = Join-Path $root 'release'
$releaseDir = Join-Path $releaseRoot 'FRONDA Cover Maker'
Remove-Item -LiteralPath $releaseDir -Recurse -Force -ErrorAction SilentlyContinue

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --contents-directory Data `
  --windowed `
  --icon "$root\resources\images\fronda.ico" `
  --manifest "$root\resources\app.manifest" `
  --name 'FRONDA Cover Maker' `
  --paths "$root\src" `
  --add-data "$root\qml;qml" `
  --add-data "$root\resources;resources" `
  --distpath "$releaseRoot" `
  --workpath "$root\build" `
  --specpath "$root\build" `
  "$root\src\fronda\main.py"

$zipPath = Join-Path $releaseRoot 'FRONDA Cover Maker_portable.zip'
$temporaryZip = "$zipPath.tmp"
Remove-Item -LiteralPath $zipPath, $temporaryZip -Force -ErrorAction SilentlyContinue
Compress-Archive -LiteralPath $releaseDir -DestinationPath $temporaryZip -CompressionLevel Optimal
Move-Item -LiteralPath $temporaryZip -Destination $zipPath -Force
Write-Host "Готово для проверки: $releaseDir"
Write-Host "ZIP-поставка: $zipPath"
