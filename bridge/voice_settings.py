"""Validated, persistent voice selection shared by speech and the picker."""
import json
import os
from pathlib import Path
import threading

VOICES = [
    {"id": f"{prefix}_{name.lower()}", "name": f"{name} — {accent}", "lang": lang}
    for prefix, accent, lang, names in [
        ("am", "American", "en-us", ("Michael", "Fenrir", "Puck", "Eric", "Liam", "Onyx", "Echo")),
        ("bm", "British", "en-gb", ("Daniel", "Fable", "George", "Lewis")),
    ] for name in names
]
CATALOG = {v['id']: v for v in VOICES}
SETTINGS_FILE = Path(__file__).resolve().parent / "voice_settings.json"
_lock = threading.Lock()

def load_voice():
    fallback = os.environ.get("KOKORO_VOICE", "am_michael")
    if fallback not in CATALOG:
        fallback = "am_michael"
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))["voice"]
        return value if value in CATALOG else fallback
    except (OSError, ValueError, KeyError, TypeError):
        return fallback

_selected = load_voice()

def current_voice():
    with _lock:
        return _selected

def select_voice(voice):
    global _selected
    if voice not in CATALOG:
        raise ValueError("Choose a voice from the list")
    with _lock:
        temporary = SETTINGS_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"voice": voice}), encoding="utf-8")
        temporary.replace(SETTINGS_FILE)
        _selected = voice
