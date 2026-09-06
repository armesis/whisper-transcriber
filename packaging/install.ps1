<#
.SYNOPSIS
    Install the built app for the current user.

.DESCRIPTION
    Copies build\dist\WhisperTranscriber to %LOCALAPPDATA%\Programs and adds a
    Start Menu shortcut. Per-user, so no administrator rights are needed, and
    nothing is written outside your own profile.

    The build folder is a build artifact and gets wiped by the next
    `build.ps1 --clean`, so running from a copy is what makes the install
    survive. Config and history live in %LOCALAPPDATA%\WhisperTranscriber and
    are deliberately left alone by -Remove.

.EXAMPLE
    .\packaging\install.ps1
    .\packaging\install.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    # Launch it once the copy is in place.
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $env:LOCALAPPDATA "Programs\WhisperTranscriber"
$shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "Whisper Transcriber.lnk"

if ($Remove) {
    Get-Process -Name "WhisperTranscriber" -ErrorAction SilentlyContinue | Stop-Process -Force
    foreach ($path in @($target, $shortcut)) {
        if (Test-Path $path) { Remove-Item -Recurse -Force $path; "Removed $path" }
    }
    "Settings and history under $env:LOCALAPPDATA\WhisperTranscriber were left in place."
    return
}

$source = Join-Path $root "build\dist\WhisperTranscriber"
if (-not (Test-Path (Join-Path $source "WhisperTranscriber.exe"))) {
    throw "Nothing built yet - run .\packaging\build.ps1 first."
}

# A running copy holds its own .exe open, so a reinstall over the top fails
# halfway and leaves a folder that is neither the old build nor the new one.
Get-Process -Name "WhisperTranscriber" -ErrorAction SilentlyContinue | ForEach-Object {
    "Stopping the running copy (pid $($_.Id))..."
    $_ | Stop-Process -Force
    $_.WaitForExit(10000) | Out-Null
}

if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

$exe = Join-Path $target "WhisperTranscriber.exe"
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$link.TargetPath = $exe
$link.WorkingDirectory = $target
$link.Description = "Push-to-talk dictation"
$link.Save()

$size = (Get-ChildItem -LiteralPath $target -Recurse -File | Measure-Object Length -Sum).Sum
"Installed to {0} ({1:N0} MB)" -f $target, ($size / 1MB)
"Start Menu shortcut: $shortcut"

if ($Start) {
    Start-Process -FilePath $exe
    "Started."
}
