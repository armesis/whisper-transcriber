#!/usr/bin/env bash
# Install a per-user Linux autostart entry for this checkout.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
LAUNCHER="$AUTOSTART_DIR/whisper-transcriber.desktop"

mkdir -p "$AUTOSTART_DIR"

# Desktop Entry's Exec grammar accepts a quoted executable path. Escape the
# two characters that are special inside those quotes so checkouts whose path
# contains spaces work as expected.
ESCAPED_RUNNER="${PROJECT_DIR//\\/\\\\}/run.sh"
ESCAPED_RUNNER="${ESCAPED_RUNNER//\"/\\\"}"

{
    printf '%s\n' '[Desktop Entry]'
    printf '%s\n' 'Type=Application'
    printf '%s\n' 'Name=Whisper Transcriber'
    printf '%s\n' 'Comment=Local push-to-talk dictation'
    printf 'Exec="%s" --background\n' "$ESCAPED_RUNNER"
    printf '%s\n' 'Terminal=false'
    printf '%s\n' 'X-GNOME-Autostart-enabled=true'
} > "$LAUNCHER"

chmod 644 "$LAUNCHER"
printf 'Installed autostart launcher: %s\n' "$LAUNCHER"
