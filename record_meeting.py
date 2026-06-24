"""Meeting NoteTaker — GUI recorder with live transcription.

Records meeting audio, shows live preview, saves .wav + timestamped .txt.
Supports multi-language auto-detection (English, Malay, Chinese, etc.).
"""
import sys, os, queue, threading, time, shutil, json
from datetime import datetime
from pathlib import Path

# --- ffmpeg setup ---
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
else:
    base = os.path.dirname(os.path.abspath(__file__))
ffmpeg_exe = os.path.join(base, "ffmpeg.exe")
if os.path.exists(ffmpeg_exe):
    dest = os.path.join(os.environ.get("TEMP", ""), "ffmpeg.exe")
    if not os.path.exists(dest):
        shutil.copy2(ffmpeg_exe, dest)
    os.environ["PATH"] = os.environ.get("TEMP", "") + os.pathsep + os.environ["PATH"]

import sounddevice as sd
import numpy as np
import whisper
from scipy.io import wavfile
import tkinter as tk
from tkinter import ttk, scrolledtext

SAMPLE_RATE = 16000
LIVE_INTERVAL = 5
SILENCE_THRESHOLD = 0.01

# Silence PyTorch's welcome messages
os.environ["WHISPER_VERBOSE"] = "0"

class NoteTakerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Meeting NoteTaker")
        self.root.geometry("700x500")
        self.root.minsize(500, 350)

        self.recording = False
        self.recorded = []
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.stream = None
        self.model = None
        self.full_audio = None

        self.input_devices = []
        self._build_ui()
        self._load_model()

    def _build_ui(self):
        # --- Top bar ---
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Mic:").pack(side="left")
        self.mic_var = tk.StringVar()
        self.mic_combo = ttk.Combobox(top, textvariable=self.mic_var, width=30, state="readonly")
        self.mic_combo.pack(side="left", padx=(2, 8))
        self._populate_devices()

        ttk.Label(top, text="Lang:").pack(side="left")
        self.lang_var = tk.StringVar(value="auto")
        lang_combo = ttk.Combobox(top, textvariable=self.lang_var,
                                  values=["auto", "en", "ms", "zh", "ta", "ja"],
                                  width=6, state="readonly")
        lang_combo.pack(side="left", padx=4)

        self.record_btn = ttk.Button(top, text="● Record", command=self.toggle_record)
        self.record_btn.pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(top, textvariable=self.status_var).pack(side="right", padx=4)

        self.model_var = tk.StringVar(value="Loading model...")
        ttk.Label(top, textvariable=self.model_var).pack(side="right", padx=4)

        # --- Live preview ---
        preview_frame = ttk.LabelFrame(self.root, text="Live Transcription", padding=4)
        preview_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.preview_text = scrolledtext.ScrolledText(preview_frame, wrap="word", height=8,
                                                       font=("Segoe UI", 10))
        self.preview_text.pack(fill="both", expand=True)

        # --- Final transcript ---
        final_frame = ttk.LabelFrame(self.root, text="Final Transcript (after stop)", padding=4)
        final_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.final_text = scrolledtext.ScrolledText(final_frame, wrap="word", height=8,
                                                     font=("Segoe UI", 10))
        self.final_text.pack(fill="both", expand=True)

    def _populate_devices(self):
        """List all input audio devices in the dropdown."""
        devices = sd.query_devices()
        self.input_devices = []
        labels = []
        default_id = sd.default.device[0]
        default_idx = 0

        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                is_default = " (default)" if i == default_id else ""
                label = f"{i}: {dev['name']}{is_default}"
                self.input_devices.append(i)
                labels.append(label)
                if i == default_id:
                    default_idx = len(labels) - 1

        self.mic_combo["values"] = labels
        if labels:
            self.mic_combo.current(default_idx)

    def _selected_device_id(self):
        idx = self.mic_combo.current()
        if idx >= 0 and idx < len(self.input_devices):
            return self.input_devices[idx]
        return sd.default.device[0]

    def _load_model(self):
        model_name = os.environ.get("WHISPER_MODEL", "large")
        self.model_var.set(f"Loading {model_name}...")

        def load():
            import whisper
            self.model = whisper.load_model(model_name)
            self.model_var.set(f"Model: {model_name}")
            self.status_var.set("Ready — press Record")

        threading.Thread(target=load, daemon=True).start()

    def toggle_record(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if self.model is None:
            self.status_var.set("Model not loaded yet — wait...")
            return

        self.recorded = []
        self.preview_text.delete("1.0", "end")
        self.final_text.delete("1.0", "end")
        self.stop_event.clear()
        self.recording = True
        self.record_btn.configure(text="■ Stop")

        lang_map = {"auto": None, "en": "en", "ms": "ms", "zh": "zh",
                    "ta": "ta", "ja": "ja"}
        self.current_lang = lang_map[self.lang_var.get()]

        device_id = self._selected_device_id()
        dev_info = sd.query_devices(device_id)
        self.status_var.set(f"Recording via: {dev_info['name']}")

        self.stream = sd.InputStream(
            device=device_id,
            samplerate=int(dev_info.get('default_samplerate', SAMPLE_RATE)),
            channels=1,
            callback=self._audio_callback,
            blocksize=int(SAMPLE_RATE * 0.5),
        )
        self.stream.start()
        threading.Thread(target=self._live_loop, daemon=True).start()
        self.status_var.set("Recording...")

    def _audio_callback(self, indata, frames, time_info, status):
        self.audio_queue.put(indata.copy())

    def _live_loop(self):
        buffer = np.array([], dtype=np.float32)
        chunk_size = SAMPLE_RATE * LIVE_INTERVAL

        while not self.stop_event.is_set():
            try:
                data = self.audio_queue.get(timeout=0.3)
                with self.lock:
                    self.recorded.append(data.copy())
                buffer = np.concatenate([buffer, data[:, 0]])
            except queue.Empty:
                continue

            while len(buffer) >= chunk_size:
                chunk = buffer[:chunk_size]
                buffer = buffer[chunk_size:]

                if np.max(np.abs(chunk)) < SILENCE_THRESHOLD:
                    continue

                result = self.model.transcribe(chunk, language=self.current_lang, task="translate", fp16=False)
                text = result["text"].strip()
                if text:
                    line = f"{datetime.now().strftime('%H:%M:%S')} {text}\n"
                    self.root.after(0, lambda t=line: self._append_preview(t))

    def _append_preview(self, text):
        self.preview_text.insert("end", text)
        self.preview_text.see("end")

    def stop_recording(self):
        self.stop_event.set()
        self.recording = False
        self.record_btn.configure(text="● Record")
        self.status_var.set("Transcribing full meeting...")
        self.root.update()

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Drain remaining queue
        while not self.audio_queue.empty():
            try:
                with self.lock:
                    self.recorded.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        # Process full audio
        with self.lock:
            if self.recorded:
                self.full_audio = np.concatenate(self.recorded)[:, 0]
            else:
                self.full_audio = np.array([], dtype=np.float32)

        duration = len(self.full_audio) / SAMPLE_RATE
        if duration < 1:
            self.status_var.set("Too short — nothing transcribed")
            return

        threading.Thread(target=self._final_transcribe, args=(duration,), daemon=True).start()

    def _final_transcribe(self, duration):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = Path.cwd() / f"meeting_{ts}.wav"
        audio_int16 = (self.full_audio * 32767).astype(np.int16)
        wavfile.write(str(wav_path), SAMPLE_RATE, audio_int16)

        lang_label = self.lang_var.get()
        result = self.model.transcribe(self.full_audio, language=self.current_lang, task="translate", fp16=False)

        txt_path = wav_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Meeting Recording — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {duration:.1f}s | Language: {lang_label}\n")
            f.write("=" * 60 + "\n\n")
            for seg in result.get("segments", []):
                st = f"{int(seg['start']//60):02d}:{int(seg['start']%60):02d}"
                et = f"{int(seg['end']//60):02d}:{int(seg['end']%60):02d}"
                f.write(f"[{st} - {et}] {seg['text'].strip()}\n")
            f.write("\n" + "=" * 60 + "\nFULL TEXT:\n" + "=" * 60 + "\n")
            f.write(result["text"])

        # Show in GUI
        full = result["text"]
        self.root.after(0, lambda: self.final_text.insert("1.0", full))
        self.root.after(0, lambda: self.status_var.set(
            f"Done — {wav_path.name} | {txt_path.name}"))
        self.root.after(0, lambda: self._flash_status("green"))

        # Also print to console
        print(f"\nSaved: {wav_path}")
        print(f"Transcript: {txt_path}")

    def _flash_status(self, color):
        pass

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = NoteTakerGUI()
    app.run()
