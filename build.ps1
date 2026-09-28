<#
.SYNOPSIS
    Empaqueta el Transmisor de Audio LAN.

.DESCRIPTION
    Sin argumentos genera dist\TransmisorAudio\ (carpeta, arranque instantaneo).
    Con -OneFile genera dist\TransmisorAudio.exe (un solo archivo, ~3 s de arranque).

.PARAMETER OneFile
    Genera un unico .exe en lugar de una carpeta.

.PARAMETER SkipDeps
    No reinstala las dependencias de requirements.txt.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -OneFile
#>
param(
    [switch]$OneFile,
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $python) {
        Write-Error "No se encontro Python. Instalalo desde python.org y volve a ejecutar."
    }
}
Write-Host "Python: $python" -ForegroundColor DarkGray

if (-not $SkipDeps) {
    Write-Host "Instalando dependencias..." -ForegroundColor Cyan
    & $python -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Error "Fallaron las dependencias." }
}

foreach ($required in @("app.py", "assets\index.html", "core\encoder.py", "core\server.py")) {
    if (-not (Test-Path -LiteralPath $required)) {
        Write-Error "Falta $required. Ejecuta el build desde la carpeta del proyecto."
    }
}

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--name", "TransmisorAudio",
    "--windowed",
    "--paths", ".",
    "--add-data", "assets;assets",
    "--collect-all", "customtkinter",
    "--collect-all", "pyaudiowpatch",
    "--hidden-import", "core.devices",
    "--hidden-import", "core.encoder",
    "--hidden-import", "core.server",
    "--hidden-import", "core.ffmpeg_bin",
    "--hidden-import", "core.applog",
    "--hidden-import", "core.config",
    "app.py"
)

if ($OneFile) {
    $arguments = @("-m", "PyInstaller", "--noconfirm", "--clean", "--name", "TransmisorAudio",
                   "--windowed", "--onefile", "--paths", ".", "--add-data", "assets;assets",
                   "--collect-all", "customtkinter", "--collect-all", "pyaudiowpatch",
                   "--hidden-import", "core.devices", "--hidden-import", "core.encoder",
                   "--hidden-import", "core.server", "--hidden-import", "core.ffmpeg_bin",
                   "--hidden-import", "core.applog", "--hidden-import", "core.config",
                   "app.py")
} else {
    $arguments = $arguments[0..($arguments.Count - 2)] + "--onedir" + $arguments[-1]
}

Write-Host "Ejecutando PyInstaller..." -ForegroundColor Cyan
& $python @arguments
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller termino con codigo $LASTEXITCODE." }

$target = if ($OneFile) { "dist\TransmisorAudio.exe" } else { "dist\TransmisorAudio\TransmisorAudio.exe" }
if (-not (Test-Path -LiteralPath $target)) { Write-Error "No se genero $target" }

$ffmpegSource = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegSource) {
    Copy-Item -LiteralPath $ffmpegSource.Source -Destination (Join-Path (Split-Path $target) "ffmpeg.exe") -Force
    Write-Host "ffmpeg.exe copiado junto al programa." -ForegroundColor DarkGray
} elseif (Test-Path -LiteralPath "ffmpeg.exe") {
    Copy-Item -LiteralPath "ffmpeg.exe" -Destination (Join-Path (Split-Path $target) "ffmpeg.exe") -Force
    Write-Host "ffmpeg.exe copiado junto al programa." -ForegroundColor DarkGray
} else {
    Write-Warning "No se encontro ffmpeg.exe. Copialo a mano junto al programa o usá el boton Examinar."
}

$size = [math]::Round((Get-Item -LiteralPath $target).Length / 1MB, 1)
Write-Host ""
Write-Host "Listo: $target ($size MB)" -ForegroundColor Green
Write-Host "Para redistributed: copiar toda la carpeta dist\TransmisorAudio\" -ForegroundColor DarkGray
