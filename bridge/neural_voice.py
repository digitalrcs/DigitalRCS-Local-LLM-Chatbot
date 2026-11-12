"""Local Kokoro speech in the ESP32's 24 kHz mono PCM format."""
from pathlib import Path
import threading
import numpy as np
from voice_settings import current_voice, CATALOG

MODEL_DIR = Path(__file__).resolve().parent / "models" / "kokoro"
_model = None
_lock = threading.RLock()


def prepare():
    """Load the local model once without generating or playing speech."""
    global _model
    with _lock:
        if _model is None:
            from kokoro_onnx import Kokoro
            _model = Kokoro(str(MODEL_DIR / "kokoro-v1.0.onnx"),
                            str(MODEL_DIR / "voices-v1.0.bin"))
        return _model

def pcm16(samples, sample_rate):
    audio = np.asarray(samples)
    if sample_rate != 24000 or audio.ndim != 1 or audio.size == 0 or audio.dtype.kind != "f":
        raise ValueError("Expected nonempty mono audio at 24000 Hz")
    if audio.size > 24000 * 60 or not np.isfinite(audio).all():
        raise ValueError("Audio is too long or contains invalid samples")
    return (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()

def synthesize(text, voice=None):
    voice = voice or current_voice()
    if voice not in CATALOG:
        raise ValueError("Unknown voice")
    with _lock:
        samples, rate = prepare().create(text, voice=voice, speed=1.0, lang=CATALOG[voice]['lang'])
        return pcm16(samples, rate)
