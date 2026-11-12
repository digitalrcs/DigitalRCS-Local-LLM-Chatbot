"""LAN voice bridge: English Whisper + LM Studio + local Kokoro speech.

LM Studio by default; optional cloud providers are selected explicitly on the PC.
"""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import wave
from functools import lru_cache
from contextlib import asynccontextmanager
from typing import Literal

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field
from settings import load_settings
from providers import generate_reply, list_models, ProviderError
from device_commands import parse_control
from voice_settings import VOICES, CATALOG, current_voice, select_voice
from listening import is_wake, is_pause, is_goodbye
from readiness import ReadinessMonitor

ROOT = Path(__file__).resolve().parent
_settings = load_settings()
LM_URL = _settings["base_url"]
LM_MODEL = _settings["model"]
STT_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")
_lock = threading.RLock()
_whisper = None
_readiness = None

def recognizer():
    global _whisper
    with _lock:
        if _whisper is None:
            from faster_whisper import WhisperModel
            _whisper = WhisperModel(STT_MODEL, device="cpu", compute_type="int8",
                                    download_root=str(ROOT / "models"))
    return _whisper


def prepare_recognition():
    recognizer()
    return "English speech model loaded. Test microphone quality on the robot."


def prepare_voice():
    if TTS_ENGINE == "kokoro":
        from neural_voice import prepare
        prepare()
        return "Local Kokoro voice model loaded. Use a preview to test speech."
    if TTS_ENGINE == "windows" and shutil.which("powershell.exe") and (ROOT / "speak.ps1").is_file():
        return "Windows speech is configured; voice generation has not been tested."
    raise ValueError("Voice engine unavailable")


def check_chat():
    config = {**_settings, "base_url": LM_URL, "model": LM_MODEL}
    if not LM_MODEL:
        raise ValueError("No model configured")
    ids = list_models(config, timeout=(2, 4))
    if LM_MODEL not in ids:
        raise ValueError("Selected model unavailable")
    if config["provider"] == "lmstudio":
        return "LM Studio is reachable and the model is listed. Reply generation has not been tested."
    if config["provider"] == "openrouter" and LM_MODEL == "openrouter/free":
        return "OpenRouter's model catalog is reachable and the free router is configured. Generation access, quota and billing have not been tested."
    return "Provider is reachable and the model is listed. Generation access, quota and billing have not been tested."


def make_readiness():
    return ReadinessMonitor({
        "recognition": (prepare_recognition, "Speech model could not load. Run START-HERE to finish speech setup; see Troubleshooting if this continues."),
        "voice": (prepare_voice, "Voice engine could not load. Check the selected engine and run START-HERE to finish voice downloads."),
        "chat": (check_chat, "Chat model is unavailable. Start LM Studio and load the selected model, or check CHANGE-PROVIDER settings for your provider."),
    })


@asynccontextmanager
async def lifespan(application):
    global _readiness
    monitor = make_readiness()
    _readiness = monitor
    monitor.start()
    try:
        yield
    finally:
        monitor.stop()


app = FastAPI(title="DigitalRCS Local LLM Chatbot", lifespan=lifespan)


@app.get("/ready")
def ready():
    # No I/O or model work in this handler. Even a failed/cold model must not
    # prevent the dashboard from explaining what is happening.
    monitor = _readiness
    return (monitor if monitor is not None else make_readiness()).snapshot()

@app.get("/health")
def health():
    return {"status": "ok", "provider": _settings["provider"], "provider_url": LM_URL, "model": LM_MODEL,
            "public_bridge_url": _settings.get("public_bridge_url", ""), "lm_studio_url": _settings.get("lm_studio_url", ""),
            "speech_model": STT_MODEL, "speech_loaded": _whisper is not None,
            "tts_engine": TTS_ENGINE,
            "tts_voice": current_voice() if TTS_ENGINE == "kokoro" else "Windows default"}

def recognize(file: UploadFile):
    audio = file.file.read(500_001)
    if len(audio) > 500_000:
        raise HTTPException(413, "Recording exceeds 500 KB")
    try:
        with wave.open(io.BytesIO(audio)) as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
                raise ValueError("Expected mono 16-bit 16 kHz WAV")
            if wav.getnframes() > 16_000 * 13:
                raise ValueError("Recording exceeds 13 seconds")
    except (wave.Error, EOFError, ValueError) as exc:
        raise HTTPException(400, "Invalid audio: " + str(exc)) from exc
    with _lock:
        segments, _ = recognizer().transcribe(io.BytesIO(audio), language="en",
            beam_size=1, vad_filter=True, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
    return text


@app.post("/v1/audio/transcriptions")
def transcribe(file: UploadFile = File(...)):
    text = recognize(file)
    return {"text": text, "control": parse_control(text), "pause": is_pause(text), "end_conversation": is_goodbye(text)}


@app.post("/v1/audio/wake")
def wake(file: UploadFile = File(...)):
    # Background room speech stays within local recognition. Never return its
    # transcript or send it to a provider. Only wake/pause phrases are allowed.
    text = recognize(file)
    return {"wake": is_wake(text), "pause": is_pause(text)}

@app.get("/")
def voice_page():
    return FileResponse(ROOT / "voices.html", media_type="text/html")

@app.get("/voices")
def voices():
    return {"voices": VOICES, "selected": current_voice(), "engine": TTS_ENGINE, "provider": _settings["provider"], "model": LM_MODEL,
            "public_bridge_url": _settings.get("public_bridge_url", ""), "lm_studio_url": _settings.get("lm_studio_url", "")}

class VoiceChoice(BaseModel):
    voice: str

@app.post("/voice")
def save_voice(body: VoiceChoice):
    try:
        select_voice(body.voice)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"selected": current_voice()}

@app.post("/voice/preview")
def preview_voice(body: VoiceChoice):
    if body.voice not in CATALOG:
        raise HTTPException(400, "Unknown voice")
    from neural_voice import synthesize as neural_speech
    pcm = neural_speech("Hello, I'm Franky, your Digital R C S assistant. I can help answer your questions, or we can just have a friendly chat. How does this voice sound to you?", voice=body.voice)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(pcm)
    return Response(output.getvalue(), media_type="audio/wav")

class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(max_length=8000)

class Chat(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=16)

@app.post("/v1/chat/completions")
def chat(body: Chat):
    config = {**_settings, "base_url": LM_URL, "model": LM_MODEL}
    try:
        text = generate_reply(config, [m.model_dump() for m in body.messages])
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "Provider unavailable or invalid reply; check local provider settings") from exc

class Speech(BaseModel):
    input: str = Field(min_length=1, max_length=1800)

def synthesize_windows(text: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="digitalrcs-voice-") as folder:
        source, target = Path(folder) / "text.txt", Path(folder) / "speech.pcm"
        source.write_text(text, encoding="utf-8")
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                        str(ROOT / "speak.ps1"), "-InputPath", str(source),
                        "-OutputPath", str(target)], check=True, capture_output=True,
                       timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        pcm = target.read_bytes()
        if not pcm or len(pcm) % 2:
            raise ValueError("Invalid PCM output")
        # Firmware holds at most 60 seconds of 24 kHz mono signed 16-bit PCM.
        if len(pcm) > 2_880_000:
            raise ValueError("Speech exceeds device buffer; request a shorter reply")
        return pcm

def synthesize(text: str) -> bytes:
    if TTS_ENGINE == "kokoro":
        from neural_voice import synthesize as neural_speech
        return neural_speech(text)
    if TTS_ENGINE == "windows":
        return synthesize_windows(text)
    raise ValueError("Unknown TTS_ENGINE; use kokoro or windows")

@app.post("/v1/audio/speech")
def speech(body: Speech):
    try:
        return Response(synthesize(body.input), media_type="application/octet-stream")
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise HTTPException(500, "Speech synthesis failed; check configured engine and model files") from exc


class Cue(BaseModel):
    kind: Literal['listening', 'followup', 'thinking', 'paused', 'welcome']


@lru_cache(maxsize=36)
def cached_cue(kind: str, engine: str, voice: str) -> bytes:
    if kind in {'listening', 'followup', 'paused'}:
        from chimes import chime
        return chime(kind)
    text = "You're welcome." if kind == 'welcome' else 'One moment, let me think.'
    if engine == 'kokoro':
        from neural_voice import synthesize as neural_speech
        return neural_speech(text, voice=voice)
    return synthesize_windows(text)


@app.post('/v1/audio/cue')
def cue(body: Cue):
    try:
        return Response(cached_cue(body.kind, TTS_ENGINE, current_voice()), media_type='application/octet-stream')
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise HTTPException(500, 'Could not prepare the local voice cue') from exc
