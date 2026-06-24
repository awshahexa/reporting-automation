"""Transcribe meeting audio to text using OpenAI Whisper."""
import sys, os
from pathlib import Path

# Add ffmpeg from TEMP to PATH if not already there
ffmpeg_dir = os.environ.get("TEMP", "")
if ffmpeg_dir and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

if len(sys.argv) < 2:
    print("Usage: python transcribe.py <audio_file> [language]")
    print("  language: optional, e.g. 'ms' for Malay, 'en' for English (auto-detect if omitted)")
    sys.exit(1)

audio_path = Path(sys.argv[1])
if not audio_path.exists():
    print(f"File not found: {audio_path}")
    sys.exit(1)

lang = sys.argv[2] if len(sys.argv) > 2 else None

import whisper

model_name = os.environ.get("WHISPER_MODEL", "base")
print(f"Loading model '{model_name}' (first run downloads ~1.5GB)...")
model = whisper.load_model(model_name)

print(f"Transcribing: {audio_path.name}...")
result = model.transcribe(str(audio_path), language=lang)

output_path = audio_path.with_suffix(".txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(result["text"])

print(f"\nDone — {len(result['text'])} chars saved to {output_path}")
print(f"\n--- Preview (first 500 chars) ---")
print(result["text"][:500])
