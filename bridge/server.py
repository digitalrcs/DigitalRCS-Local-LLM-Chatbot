"""LAN voice bridge: English Whisper + LM Studio + local Kokoro speech.

No OpenAI cloud calls. Configure LM_STUDIO_URL and LM_STUDIO_MODEL via environment.
"""
import io
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import wave

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field
from settings import load_settings
from device_commands import parse_control
from voice_settings import VOICES, CATALOG, current_voice, select_voice

ROOT = Path(__file__).resolve().parent
_settings = load_settings()
LM_URL = _settings["lm_studio_url"]
LM_MODEL = _settings["lm_studio_model"]
STT_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")
app = FastAPI(title="DigitalRCS Local LLM Chatbot")
_lock = threading.Lock()
_whisper = None

def recognizer():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(STT_MODEL, device="cpu", compute_type="int8",
                                download_root=str(ROOT / "models"))
    return _whisper

@app.get("/health")
def health():
    return {"status": "ok", "lm_studio_url": LM_URL, "model": LM_MODEL,
            "speech_model": STT_MODEL, "speech_loaded": _whisper is not None,
            "tts_engine": TTS_ENGINE,
            "tts_voice": current_voice() if TTS_ENGINE == "kokoro" else "Windows default"}

@app.post("/v1/audio/transcriptions")
def transcribe(file: UploadFile = File(...)):
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
    return {"text": text, "control": parse_control(text)}

@app.get("/")
def voice_page():
    return FileResponse(ROOT / "voices.html", media_type="text/html")

@app.get("/voices")
def voices():
    return {"voices": VOICES, "selected": current_voice(), "engine": TTS_ENGINE}

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
    if not LM_MODEL:
        raise HTTPException(503, "Run START-HERE to select an LM Studio chat model")
    payload = {"model": LM_MODEL, "messages": [m.model_dump() for m in body.messages],
               "stream": False, "max_tokens": 400}
    headers = {}
    if os.environ.get("LM_STUDIO_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["LM_STUDIO_TOKEN"]
    try:
        response = requests.post(LM_URL + "/chat/completions", json=payload,
                                 headers=headers, timeout=(5, 50))
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Empty model reply")
        # Do not speak chain-of-thought emitted by some local models.
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        if "<think>" in text or not text:
            raise ValueError("Model did not return a final answer")
        return {"choices": [{"message": {"role": "assistant", "content": text}}]}
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "LM Studio unavailable or invalid reply; check server and model") from exc

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
