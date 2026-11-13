"""LAN voice bridge: English Whisper + LM Studio + local Kokoro speech.

LM Studio by default; optional cloud providers are selected explicitly on the PC.
"""
import io
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from functools import lru_cache
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, FileResponse, StreamingResponse
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from settings import load_settings
from providers import generate_reply, list_models, stream_reply, ProviderError
from conversation import frame, stream_reply_frames
from device_commands import parse_control
from voice_settings import VOICES, CATALOG, current_voice, select_voice
from listening import is_wake, is_pause, is_goodbye
from readiness import ReadinessMonitor

ROOT = Path(__file__).resolve().parent
_settings = load_settings()
LM_URL = _settings["base_url"]
LM_MODEL = _settings["model"]
STT_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
# Wake checks hear two-word phrases, so a smaller model is enough. Set
# WAKE_WHISPER_MODEL to the same name as WHISPER_MODEL to share one model.
WAKE_STT_MODEL = os.environ.get("WAKE_WHISPER_MODEL", "tiny.en")
# "cpu" keeps the GPU free for the chat model; "cuda" suits a spare GPU.
STT_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")
log = logging.getLogger("uvicorn.error")
# Questions and wake checks use separate models and locks, so a question never
# waits behind a background wake check.
_lock = threading.RLock()
_wake_lock = threading.RLock()
_whisper = None
_wake_whisper = None
_readiness = None


@contextmanager
def timed(stage):
    """Log how long one stage of a conversation took."""
    started = time.perf_counter()
    try:
        yield
    finally:
        log.info("Franky timing: %s %.2f s", stage, time.perf_counter() - started)


def load_whisper(name):
    from faster_whisper import WhisperModel
    compute = "float16" if STT_DEVICE == "cuda" else "int8"
    bundled = ROOT / "models" / ("whisper-" + name) if name in {"base.en", "tiny.en"} else None
    if bundled is not None and (bundled / "model.bin").is_file():
        # The Windows installer supplies complete local models. Loading these
        # paths needs neither Hub authentication nor a metadata network call.
        return WhisperModel(str(bundled), device=STT_DEVICE, compute_type=compute, local_files_only=True)
    return WhisperModel(name, device=STT_DEVICE, compute_type=compute, download_root=str(ROOT / "models"))


def recognizer():
    global _whisper
    with _lock:
        if _whisper is None:
            _whisper = load_whisper(STT_MODEL)
    return _whisper


def wake_recognizer():
    """Return (model, lock) for wake checks; fall back to the question model."""
    global _wake_whisper
    if WAKE_STT_MODEL == STT_MODEL:
        return recognizer(), _lock
    with _wake_lock:
        if _wake_whisper is None:
            try:
                _wake_whisper = load_whisper(WAKE_STT_MODEL)
            except Exception:
                # Offline or missing download: keep wake detection working.
                log.warning("Wake model %s unavailable; using %s for wake checks", WAKE_STT_MODEL, STT_MODEL)
                _wake_whisper = False
        if _wake_whisper is False:
            return recognizer(), _lock
        return _wake_whisper, _wake_lock


def prepare_recognition():
    recognizer()
    wake_recognizer()
    return "English speech models loaded. Test microphone quality on the robot."


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
    return {"status": "ok", "instance_id": os.environ.get("FRANKY_INSTANCE_ID", ""),
            "provider": _settings["provider"], "provider_url": LM_URL, "model": LM_MODEL,
            "public_bridge_url": _settings.get("public_bridge_url", ""), "lm_studio_url": _settings.get("lm_studio_url", ""),
            "speech_model": STT_MODEL, "speech_loaded": _whisper is not None,
            "wake_speech_model": WAKE_STT_MODEL, "speech_device": STT_DEVICE,
            "tts_engine": TTS_ENGINE,
            "tts_voice": current_voice() if TTS_ENGINE == "kokoro" else "Windows default"}

def recognize(file: UploadFile, wake=False):
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
    model, lock = wake_recognizer() if wake else (recognizer(), _lock)
    with lock, timed("wake check" if wake else "speech to text"):
        segments, _ = model.transcribe(io.BytesIO(audio), language="en", beam_size=1, vad_filter=True,
                                       condition_on_previous_text=False, without_timestamps=True)
        text = " ".join(s.text.strip() for s in segments).strip()
    return text


def question_metadata(text):
    """Local, deterministic flags for one transcribed question."""
    return {"text": text, "control": parse_control(text), "pause": is_pause(text), "end_conversation": is_goodbye(text)}


@app.post("/v1/audio/transcriptions")
def transcribe(file: UploadFile = File(...)):
    return question_metadata(recognize(file))


@app.post("/v1/audio/wake")
def wake(file: UploadFile = File(...)):
    # Background room speech stays within local recognition. Never return its
    # transcript or send it to a provider. Only wake/pause phrases are allowed.
    text = recognize(file, wake=True)
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
        with timed("chat reply"):
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
        with timed("speech"):
            return Response(synthesize(body.input), media_type="application/octet-stream")
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        raise HTTPException(500, "Speech synthesis failed; check configured engine and model files") from exc


class Cue(BaseModel):
    kind: Literal['listening', 'followup', 'thinking', 'paused', 'welcome']


@lru_cache(maxsize=36)
def cached_cue(kind: str, engine: str, voice: str) -> bytes:
    if kind in {'listening', 'followup', 'thinking', 'paused'}:
        from chimes import chime
        return chime('listening' if kind == 'thinking' else kind)
    text = "You're welcome."
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


_history = TypeAdapter(list[Message])


def parse_history(raw: str):
    """Validate the robot's system prompt and earlier turns (JSON message list)."""
    try:
        messages = _history.validate_python(json.loads(raw or "[]"))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, "Invalid conversation history") from exc
    if len(messages) > 15:
        raise HTTPException(400, "Conversation history is too long")
    return [m.model_dump() for m in messages]


def converse_frames(meta, history, stop=None):
    """Yield the frame stream for one transcribed question."""
    stop = stop or threading.Event()
    try:
        if stop.is_set():
            return
        yield frame("J", meta)
        text = meta["text"]
        if meta["pause"]:
            cue = cached_cue("paused", TTS_ENGINE, current_voice())
            if not stop.is_set():
                yield frame("C", cue)
                yield frame("E", {})
            return
        if meta["end_conversation"]:
            # Welcome speech may need model loading too; use the same heartbeat
            # and error handling as ordinary speech without calling a provider.
            yield from stream_reply_frames(iter(["You're welcome."]),
                lambda _: cached_cue("welcome", TTS_ENGINE, current_voice()), stop=stop)
            return
        if meta["control"] is not None or not text or len(text) > 2000:
            # The robot applies device commands itself and reports empty speech.
            if not stop.is_set():
                yield frame("E", {})
            return
        config = {**_settings, "base_url": LM_URL, "model": LM_MODEL}
        pieces = stream_reply(config, [*history, {"role": "user", "content": text}], stop=stop)
        yield from stream_reply_frames(pieces, synthesize, stop=stop,
            cue=cached_cue("thinking", TTS_ENGINE, current_voice()))
    except Exception:
        if not stop.is_set():
            yield frame("E", {"error": "Conversation audio unavailable. Check the bridge."})


class ConversationResponse(StreamingResponse):
    """Own cancellation even when Starlette does not close a sync generator."""

    def __init__(self, frames, stop):
        super().__init__(frames, media_type="application/octet-stream")
        self.frames, self.stop = frames, stop

    async def __call__(self, scope, receive, send):
        async def receive_and_cancel():
            message = await receive()
            if message["type"] == "http.disconnect":
                self.stop.set()
            return message

        try:
            await super().__call__(scope, receive_and_cancel, send)
        finally:
            # Heartbeats and timed queue waits release the threadpool iterator;
            # a provider blocked in a socket read retains its read timeout.
            self.stop.set()
            self.frames.close()


@app.post("/v1/converse")
def converse(file: UploadFile = File(...), messages: str = Form("[]")):
    """One request per spoken question: transcript, chime and streamed speech.

    Errors found before streaming starts return normal HTTP errors. Once the
    stream starts, errors arrive in the final E frame.
    """
    history = parse_history(messages)
    meta = question_metadata(recognize(file))
    try:
        frame("J", meta)
    except ValueError as exc:
        raise HTTPException(400, "Transcription exceeds the supported frame size") from exc
    stop = threading.Event()
    return ConversationResponse(converse_frames(meta, history, stop), stop)
