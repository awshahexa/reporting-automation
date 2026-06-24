"""Live microphone transcription with multi-language auto-detection.

Records from mic in 5s chunks and transcribes with Whisper (auto language).
Press Ctrl+C to stop.

Usage:
  python live_transcribe.py              # auto-detect language per chunk
  python live_transcribe.py ms           # force Malay
  python live_transcribe.py en,ms        # hint: English + Malay
"""
import sys, os, queue, threading, time
from datetime import datetime

os.environ["PATH"] = os.environ.get("TEMP", "") + os.pathsep + os.environ["PATH"]

import sounddevice as sd
import numpy as np
import whisper

SAMPLE_RATE = 16000
CHUNK_SEC = 5          # seconds per transcription chunk
SILENCE_THRESHOLD = 0.01  # skip silent chunks

model_name = os.environ.get("WHISPER_MODEL", "base")
print(f"Loading model '{model_name}'...")
model = whisper.load_model(model_name)

language = sys.argv[1] if len(sys.argv) > 1 else None
# Task: "transcribe" (no timestamps) or "translate" (to English)
task = "transcribe"

print(f"Language: {language or 'auto-detect per chunk'}")
print(f"Mic: {sd.query_devices(sd.default.device[0], 'input')['name']}")
print(f"Recording every {CHUNK_SEC}s — Ctrl+C to stop\n")

audio_queue = queue.Queue()
stop_event = threading.Event()

def audio_callback(indata, frames, time_info, status):
    audio_queue.put(indata.copy())

def process_loop():
    """Thread: pulls audio chunks, transcribes, prints."""
    buffer = np.array([], dtype=np.float32)
    chunk_samples = SAMPLE_RATE * CHUNK_SEC

    while not stop_event.is_set():
        try:
            data = audio_queue.get(timeout=0.5)
            buffer = np.concatenate([buffer, data[:, 0]])
        except queue.Empty:
            continue

        while len(buffer) >= chunk_samples:
            chunk = buffer[:chunk_samples]
            buffer = buffer[chunk_samples:]

            # Skip silence
            if np.max(np.abs(chunk)) < SILENCE_THRESHOLD:
                continue

            ts = datetime.now().strftime("%H:%M:%S")
            result = model.transcribe(
                chunk,
                language=language,
                task=task,
                fp16=False,
            )
            text = result["text"].strip()
            detected = result.get("language", "")
            if text:
                lang_tag = f"[{detected}] " if not language else ""
                print(f"{ts} {lang_tag}{text}")

try:
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        callback=audio_callback,
        blocksize=int(SAMPLE_RATE * 0.5),
    )
    t = threading.Thread(target=process_loop, daemon=True)
    t.start()

    with stream:
        while not stop_event.is_set():
            time.sleep(0.1)
except KeyboardInterrupt:
    stop_event.set()
    print("\nStopped.")
