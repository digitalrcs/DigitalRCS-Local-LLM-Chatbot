# Architecture and API

The included Python FastAPI bridge connects a compatible audio client to faster-whisper (English recognition), LM Studio (chat), and Kokoro (speech). All model inference can run locally after downloads. Device controls are parsed using explicit rules; model replies are not executed as hardware commands.

## Configuration

The wizard writes `bridge/config.json`, which Git and the release builder exclude. `LM_STUDIO_URL` and `LM_STUDIO_MODEL` environment variables override that file. `LM_STUDIO_TOKEN` optionally supplies authentication to LM Studio. Restart the bridge after changes. The default server address is `http://127.0.0.1:1234/v1`; no chat model is selected until setup.

`WHISPER_MODEL` defaults to `base.en`. `TTS_ENGINE` defaults to `kokoro`; `windows` selects the optional Windows SAPI fallback. The voice picker requires Kokoro. Voice choice persists in ignored `bridge/voice_settings.json`. Models live in ignored `bridge/models/`.

## Endpoints

| Route | Request | Response |
| --- | --- | --- |
| GET `/health` | None | Service status and configured model details; not an upstream readiness probe |
| GET `/` | None | Voice picker |
| GET `/voices` | None | Voice catalog and selected ID |
| POST `/voice` | JSON `{"voice":"am_michael"}` | Persisted selection |
| POST `/voice/preview` | Same voice JSON | Playable WAV preview; does not save selection |
| POST `/v1/audio/transcriptions` | Multipart `file`: mono 16-bit 16 kHz WAV, <=13 seconds and <=500 KB | `text` and optional deterministic `control` metadata |
| POST `/v1/chat/completions` | JSON `messages` with system/user/assistant roles | One assistant message; non-streaming |
| POST `/v1/audio/speech` | JSON `{"input":"Hello"}` | Raw signed little-endian PCM16, mono 24 kHz, <=60 seconds |

The `/v1` naming is a limited compatibility contract, not a complete implementation of any cloud API. Speech responses are raw PCM, not WAV; voice previews are WAV. Chat requests accept 1–16 messages of at most 8,000 characters each and request up to 400 generated tokens from LM Studio.

## Device controls

The bridge recognizes supported volume and brightness phrases and returns metadata. Compatible firmware must apply limits, update hardware, persist settings, and confirm the resulting value. The prototype uses volume 0–100 and brightness 10–100. “Increase volume ten percent” means ten percentage points, not a proportional multiplication. Unsupported commands continue as ordinary chat. The public package contains no firmware that applies these actions.

## Limits

CPU speech recognition is serialized. Speech generation is serialized to protect the local model. This is a home prototype service, not a multi-user hosted platform. HTTP endpoints have no login or user accounts. There is no automatic Windows service installation, remote management, cloud ChatGPT setup, or Internet exposure configuration.
