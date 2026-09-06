"""Download a CTranslate2 Whisper model into ./models so a build can vendor it.

Without this the app fetches its model on first run, which keeps the download
small but needs a working internet connection the first time it starts. Run
this instead to bake the model into the build:

    python packaging/fetch_model.py base.en

Sizes are dominated by the weights, so this is the one knob that really moves
the installed footprint. Float16 is what the official repos publish; on CPU
CTranslate2 quantizes it to int8 while loading, so the extra bytes buy nothing
but disk. --int8 converts the weights ahead of time and roughly halves them, at
the cost of a heavyweight one-off build dependency (transformers + torch).
"""
import argparse
import shutil
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# name -> (CTranslate2 repo on the Hub, OpenAI repo for --int8 conversion)
CATALOG = {
    "tiny": ("Systran/faster-whisper-tiny", "openai/whisper-tiny"),
    "tiny.en": ("Systran/faster-whisper-tiny.en", "openai/whisper-tiny.en"),
    "base": ("Systran/faster-whisper-base", "openai/whisper-base"),
    "base.en": ("Systran/faster-whisper-base.en", "openai/whisper-base.en"),
    "small": ("Systran/faster-whisper-small", "openai/whisper-small"),
    "small.en": ("Systran/faster-whisper-small.en", "openai/whisper-small.en"),
    "distil-small.en": ("Systran/faster-distil-whisper-small.en", None),
    "medium": ("Systran/faster-whisper-medium", "openai/whisper-medium"),
    "large-v3": ("Systran/faster-whisper-large-v3", "openai/whisper-large-v3"),
}

# Everything CTranslate2 and the tokenizer need at inference time. The repos also
# carry README images and PyTorch checkpoints we would otherwise pull down.
KEEP = ["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"]


def download(name: str, out: Path) -> None:
    from huggingface_hub import snapshot_download

    repo, _ = CATALOG[name]
    print(f"Downloading {repo} -> {out}")
    snapshot_download(repo_id=repo, local_dir=str(out), allow_patterns=KEEP)


def convert_int8(name: str, out: Path) -> None:
    try:
        from ctranslate2.converters import TransformersConverter
    except ImportError:  # pragma: no cover - ctranslate2 is a hard dependency
        raise SystemExit("ctranslate2 is not installed")

    repo, source = CATALOG[name]
    if source is None:
        raise SystemExit(f"No upstream checkpoint registered for '{name}'; download it as float16 instead.")
    try:
        import transformers  # noqa: F401
    except ImportError:
        raise SystemExit(
            "int8 conversion needs the original checkpoint, which means transformers and torch.\n"
            "They are build-time only - nothing extra is shipped:\n"
            "    pip install transformers torch --index-url https://download.pytorch.org/whl/cpu"
        )
    print(f"Converting {source} to int8 -> {out}")
    TransformersConverter(source, copy_files=["tokenizer.json", "preprocessor_config.json"]).convert(
        str(out), quantization="int8", force=True
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", choices=sorted(CATALOG), help="which model to place in ./models")
    parser.add_argument("--int8", action="store_true", help="quantize the weights to int8 (about half the size)")
    parser.add_argument("--name", help="directory name under ./models (defaults to the model name)")
    args = parser.parse_args()

    out = MODELS_DIR / (args.name or args.model)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    if args.int8:
        convert_int8(args.model, out)
    else:
        download(args.model, out)

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{out} is {total / 1e6:.0f} MB")
    print(f"Build it in with:  packaging/build.ps1 -Model {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
