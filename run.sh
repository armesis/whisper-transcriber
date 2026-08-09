#!/usr/bin/env bash
# Launcher for whisper-transcriber.
#
# ctranslate2 dlopen()s libcublas.so.12 at encode time. Ubuntu ships cuDNN but
# not cuBLAS, so it comes from the nvidia-cublas-cu12 pip wheel in the venv -
# which isn't on the default library search path. Without this the model loads
# fine and then every transcription dies with "Library libcublas.so.12 is not
# found or cannot be loaded".
set -euo pipefail

# readlink -f so the ~/.local/bin/whisper-transcriber symlink resolves to the
# real checkout - otherwise DIR lands in the symlink's directory and the venv
# lookup below fails.
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
NVIDIA="$DIR/.venv/lib/python3.12/site-packages/nvidia"
export LD_LIBRARY_PATH="$NVIDIA/cublas/lib:$NVIDIA/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"

exec "$DIR/.venv/bin/python" "$DIR/main.py"
