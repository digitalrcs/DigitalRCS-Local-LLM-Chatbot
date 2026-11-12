"""Streamed spoken replies: model text -> sentences -> speech, in parallel.

Three parts run at the same time and are joined by queues:

  chat thread   reads model text and puts whole sentences on `sentences`
  voice thread  turns each sentence into PCM and puts it on `audio`
  caller        reads `audio` and sends frames to the robot

Workers signal completion with None. Bounded queues use timed waits so a shared
threading.Event releases both workers when the robot disconnects or presses
Stop; an inference or network call already running must return before cleanup.

Wire format (one frame): 1 byte type, 4 bytes little-endian length, payload.
  J  JSON metadata about the question (transcript and local flags)
  C  cue audio (chime), PCM16 mono 24 kHz
  T  UTF-8 text of the sentence that the next P frame speaks
  P  speech audio, PCM16 mono 24 kHz
  H  empty heartbeat while waiting for speech
  E  JSON end of reply: {"reply": text} or {"error": message, "partial_reply": text}
"""
import json
import logging
import queue
import re
import struct
import threading
import time

MAX_SPOKEN_CHARACTERS = 1800
MAX_TEXT_FRAME_BYTES = 8192
MIN_SENTENCE_CHARACTERS = 12
QUEUE_POLL_SECONDS = 0.1
HEARTBEAT_SECONDS = 0.5
log = logging.getLogger("uvicorn.error")

# End of a sentence: ., ! or ? (optionally followed by closing quotes or
# brackets), then white space, then something that starts a new sentence.
_BOUNDARY = re.compile(r"""[.!?]+["')\]]*\s+(?=["'(\[]?[A-Z0-9])|\n+""")


def frame(kind, payload):
    """Encode one frame. kind is a one-letter type; payload is bytes, str or dict."""
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    elif isinstance(payload, str):
        payload = payload.encode("utf-8")
    if kind in {"J", "T", "E"} and len(payload) > MAX_TEXT_FRAME_BYTES:
        raise ValueError("Reply exceeds the supported frame size")
    if kind == "H" and payload:
        raise ValueError("Heartbeat frames must be empty")
    return kind.encode("ascii") + struct.pack("<I", len(payload)) + payload


def split_sentences(buffer):
    """Split complete sentences off the front of buffer.

    Returns (sentences, remainder). The remainder is text whose sentence has not
    ended yet. Very short pieces such as "Hi." are joined to the next sentence
    so the voice keeps natural rhythm.
    """
    sentences, start = [], 0
    for match in _BOUNDARY.finditer(buffer):
        candidate = buffer[start:match.end()].strip()
        if len(candidate) >= MIN_SENTENCE_CHARACTERS:
            sentences.append(candidate)
            start = match.end()
    return sentences, buffer[start:]


def put_until_stopped(output, item, stop):
    """Apply bounded backpressure without trapping a cancelled worker."""
    while not stop.is_set():
        try:
            output.put(item, timeout=QUEUE_POLL_SECONDS)
            return True
        except queue.Full:
            pass
    return False


def chat_worker(pieces, sentences, stop):
    """Collect streamed text into sentences; put ("error", message) on failure."""
    buffer, accepted = "", []

    def enqueue(sentence):
        reply = " ".join([*accepted, sentence])
        if len(reply) > MAX_SPOKEN_CHARACTERS:
            raise ValueError("Reply exceeds the spoken-text limit")
        # Check the sentence and final history before committing it to speech.
        frame("T", sentence)
        frame("E", {"reply": reply})
        if not put_until_stopped(sentences, ("text", sentence), stop):
            return False
        accepted.append(sentence)
        return True

    try:
        for piece in pieces:
            if stop.is_set():
                return
            buffer += piece
            done, buffer = split_sentences(buffer)
            for sentence in done:
                if not enqueue(sentence):
                    return
            pending = [buffer.strip()] if buffer.strip() else []
            if len(" ".join([*accepted, *pending])) > MAX_SPOKEN_CHARACTERS:
                raise ValueError("Reply exceeds the spoken-text limit")
        if buffer.strip() and not stop.is_set():
            enqueue(buffer.strip())
    except Exception as exc:  # The provider layer already uses safe messages.
        message = str(exc)[:160] if isinstance(exc, ValueError) else "Chat service unavailable"
        put_until_stopped(sentences, ("error", message), stop)
    finally:
        try:
            close = getattr(pieces, "close", None)
            if close:
                close()  # Only its owning thread closes the provider iterator.
        except Exception:
            put_until_stopped(sentences, ("error", "Chat service unavailable"), stop)
        finally:
            put_until_stopped(sentences, None, stop)


def voice_worker(sentences, audio, synthesize, stop):
    """Turn each sentence into speech; errors pass through unchanged."""
    try:
        while not stop.is_set():
            try:
                item = sentences.get(timeout=QUEUE_POLL_SECONDS)
            except queue.Empty:
                continue
            if item is None:
                return
            kind, value = item
            if kind == "error":
                put_until_stopped(audio, item, stop)
                return
            try:
                pcm = synthesize(value)
                if not pcm or len(pcm) % 2:
                    raise ValueError("Invalid speech audio")
                if not put_until_stopped(audio, ("speech", value, pcm), stop):
                    return
            except Exception:
                put_until_stopped(audio, ("error", "Voice service unavailable"), stop)
                return
    finally:
        put_until_stopped(audio, None, stop)


def stream_reply_frames(pieces, synthesize, stop=None, cue=None):
    """Yield frames for a spoken reply while the model is still writing it.

    pieces is an iterator of model text. synthesize(text) returns PCM bytes.
    cue, if given, is PCM sent first so the robot plays it while it waits.
    The HTTP response owns stop, including disconnects; direct callers close
    this iterator when abandoning it.
    """
    stop = stop or threading.Event()
    sentences, audio = queue.Queue(maxsize=4), queue.Queue(maxsize=2)
    started = time.perf_counter()
    workers = [
        threading.Thread(target=chat_worker, args=(pieces, sentences, stop), daemon=True, name="franky-chat"),
        threading.Thread(target=voice_worker, args=(sentences, audio, synthesize, stop), daemon=True, name="franky-voice"),
    ]
    for worker in workers:
        worker.start()
    spoken, error, first_audio = [], None, None
    try:
        if cue and not stop.is_set():
            yield frame("C", cue)
        heartbeat_at = time.monotonic() + HEARTBEAT_SECONDS
        while not stop.is_set():
            try:
                item = audio.get(timeout=QUEUE_POLL_SECONDS)
            except queue.Empty:
                if not stop.is_set() and time.monotonic() >= heartbeat_at:
                    yield frame("H", b"")
                    heartbeat_at = time.monotonic() + HEARTBEAT_SECONDS
                continue
            if stop.is_set():
                return
            if item is None:
                break
            if item[0] == "error":
                error = error or item[1]
                break
            _, text, pcm = item
            if first_audio is None:
                first_audio = time.perf_counter() - started
            yield frame("T", text)
            if stop.is_set():
                return
            yield frame("P", pcm)
            spoken.append(text)
            heartbeat_at = time.monotonic() + HEARTBEAT_SECONDS
        if stop.is_set():
            return
        if error:
            end = {"error": error}
            if spoken:
                end["partial_reply"] = " ".join(spoken)
            try:
                terminal = frame("E", end)
            except ValueError:
                terminal = frame("E", {"error": error})
            yield terminal
        else:
            yield frame("E", {"reply": " ".join(spoken)})
        log.info("Franky timing: first speech %.2f s, full reply %.2f s, %d sentences",
                 first_audio or 0.0, time.perf_counter() - started, len(spoken))
    finally:
        # The HTTP response also sets this event directly on disconnect.
        stop.set()
