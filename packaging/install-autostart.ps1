<#
.SYNOPSIS
    Start the packaged app quietly in the tray at every Windows login.

.DESCRIPTION
    Creates a shortcut in the current user's Startup folder pointing at the
    built WhisperTranscriber.exe with --background, so it comes up in the tray
    without a window. Per-user, so it needs no administrator rights.
    Run with -Remove to undo it.
#>
[CmdletBinding()]
param(
    [string]$ExePath = (Join-Path (Split-Path -Parent $PSScriptRoot) "build\dist\WhisperTranscriber\WhisperTranscriber.exe"),
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$link = Join-Path ([Environment]::GetFolderPath("Startup")) "WhisperTranscriber.lnk"

if ($Remove) {
    if (Test-Path $link) { Remove-Item $link; "Removed $link" } else { "Nothing to remove." }
    return
}

if (-not (Test-Path $ExePath)) { throw "No executable at $ExePath - run packaging\build.ps1 first." }

$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
$shortcut.TargetPath = (Resolve-Path $ExePath).Path
$shortcut.Arguments = "--background"
$shortcut.WorkingDirectory = Split-Path -Parent (Resolve-Path $ExePath).Path
$shortcut.Description = "Push-to-talk dictation"
$shortcut.Save()

"Created $link"
"Whisper will start in the tray at your next login."
