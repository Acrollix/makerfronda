# Upload FRONDA Cover Maker to GitHub without storing a token in the project.
# Run this file locally; it asks for a fresh fine-grained PAT in the console.
[CmdletBinding()]
param(
    [string]$Repository = 'https://github.com/Acrollix/makerfronda.git'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git не найден. Установите Git for Windows: https://git-scm.com/download/win'
}

$tokenSecure = Read-Host 'Вставьте НОВЫЙ GitHub fine-grained token (не сохраняется)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSecure)
$token = $null
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($token)) { throw 'Токен не введён.' }

    if (-not (Test-Path -LiteralPath (Join-Path $root '.git'))) {
        & git init
        & git branch -M main
    }

    if (-not (& git config user.name)) { & git config user.name 'Acrollix' }
    if (-not (& git config user.email)) { & git config user.email 'Acrollix@users.noreply.github.com' }

    $origin = (& git remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $origin) {
        & git remote add origin $Repository
    } elseif ($origin -ne $Repository) {
        throw "Уже настроен другой origin: $origin"
    }

    # Only distributable source is staged; local build and export folders stay out of Git.
    & git add -- .gitignore pyproject.toml src qml resources scripts tests .github
    & git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        & git commit -m 'Add FRONDA Cover Maker with macOS ARM64 build'
    }

    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$token"))
    & git -c "http.extraheader=AUTHORIZATION: basic $basic" push -u origin main
    if ($LASTEXITCODE -ne 0) { throw 'GitHub отклонил push. Проверьте права токена Contents: Read and write.' }

    Write-Host ''
    Write-Host 'Готово. GitHub Actions уже начал сборку macOS ARM64.' -ForegroundColor Green
    Write-Host 'Артефакт появится во вкладке Actions репозитория makerfronda.' -ForegroundColor Green
}
finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $token = $null
}
