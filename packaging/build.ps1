<#
.SYNOPSIS
    Build WhisperTranscriber into a self-contained Windows folder.

.DESCRIPTION
    Produces build\dist\WhisperTranscriber, which needs no Python, no Visual C++
    redistributable and no GPU: it runs on any 64-bit Windows 10 or 11 machine.
    CUDA is still used automatically when the machine happens to have it.

    By default no model is bundled - the app downloads the one named in
    config.json on first run and caches it under %LOCALAPPDATA%. That keeps the
    thing you distribute small. Pass -Model to bake one in instead, after
    fetching it with packaging\fetch_model.py.

.EXAMPLE
    .\packaging\build.ps1
    .\packaging\build.ps1 -Model base.en -Zip
    .\packaging\build.ps1 -WithVad -Console
#>
[CmdletBinding()]
param(
    # Directory name under .\models to bundle. Empty means download on first run.
    [string]$Model = "",
    # Bundle onnxruntime for the Silero VAD (~45 MB). Without it the app uses the
    # energy-based silence trim in transcriber/model.py.
    [switch]$WithVad,
    # Keep a console window so print() output is visible. For debugging only.
    [switch]$Console,
    # Ship every Qt DLL the hook found, including the software OpenGL fallback.
    [switch]$KeepAllQt,
    # Also produce a distributable .zip next to the folder.
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No virtualenv at $python - create it and pip install -r requirements.txt" }

$env:WT_MODEL = $Model
$env:WT_VAD = if ($WithVad) { "1" } else { "0" }
$env:WT_CONSOLE = if ($Console) { "1" } else { "0" }
$env:WT_KEEP_ALL_QT = if ($KeepAllQt) { "1" } else { "0" }

# PyInstaller logs progress on stderr, which an ErrorActionPreference of Stop
# would turn into a terminating error before it ever finishes. Judge it by its
# exit code instead.
$ErrorActionPreference = "Continue"
& $python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $root "build\dist") `
    --workpath (Join-Path $root "build\work") `
    (Join-Path $PSScriptRoot "whisper.spec")
$built = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($built -ne 0) { throw "PyInstaller failed with exit code $built" }

$dist = Join-Path $root "build\dist\WhisperTranscriber"
$size = (Get-ChildItem -LiteralPath $dist -Recurse -File | Measure-Object Length -Sum).Sum
"{0}`nInstalled size: {1:N0} MB" -f $dist, ($size / 1MB)

# A build that cannot construct its own widgets is not a build. Catch that here
# rather than on someone else's machine.
$test = Start-Process -FilePath (Join-Path $dist "WhisperTranscriber.exe") -ArgumentList "--selftest" -PassThru
if (-not $test.WaitForExit(180000)) { $test.Kill(); throw "Self-test timed out" }
if ($test.ExitCode -ne 0) { throw "Self-test failed with exit code $($test.ExitCode)" }
"Self-test passed."

if ($Zip) {
    # Not $zip: PowerShell variable names are case-insensitive, so that would
    # assign a path over the -Zip switch parameter and fail on its type.
    $zipPath = Join-Path $root "build\WhisperTranscriber.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    Compress-Archive -Path $dist -DestinationPath $zipPath -CompressionLevel Optimal
    "Download size:  {0:N0} MB  ({1})" -f ((Get-Item $zipPath).Length / 1MB), $zipPath
}
