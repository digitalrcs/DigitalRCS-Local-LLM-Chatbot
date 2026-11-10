# Architecture and API

The included Python FastAPI bridge connects a compatible audio client to faster-whisper (English recognition), LM Studio by default (chat), and Kokoro (speech). All model inference can run locally after downloads. Optional OpenAI, OpenRouter free-model, and Gemini adapters are selected explicitly on the PC; see [PROVIDERS.md](PROVIDERS.md). Device controls are parsed using explicit rules; model replies are not executed as hardware commands.

## Configuration

The wizard writes `bridge/config.json`, which Git and the release builder exclude. `LM_STUDIO_URL` and `LM_STUDIO_MODEL` environment variables override that file. `LM_STUDIO_TOKEN` optionally supplies authentication to LM Studio. Restart the bridge after changes. The default server address is `http://127.0.0.1:1234/v1`; no chat model is selected until setup.

`WHISPER_MODEL` defaults to `base.en`. `TTS_ENGINE` defaults to `kokoro`; `windows` selects the optional Windows SAPI fallback. The voice picker requires Kokoro. Voice choice persists in ignored `bridge/voice_settings.json`. Models live in ignored `bridge/models/`.

## Endpoints

| Route | Request | Response |
| --- | --- | --- |
| GET `/health` | None | Service status and configured model details; not an upstream readiness probe |
| GET `/` | None | Voice picker |
| GET `/voices` | None | Voice catalog and selected ID |
| POST `/voice` | JSON `{"voice":"am_liam"}` | Persisted selection |
| POST `/voice/preview` | Same voice JSON | Playable WAV preview; does not save selection |
| POST `/v1/audio/transcriptions` | Multipart `file`: mono 16-bit 16 kHz WAV, <=13 seconds and <=500 KB | `text` and optional deterministic `control` metadata |
| POST `/v1/audio/wake` | Same local WAV contract | Boolean `wake` and `pause` flags only; no transcript or provider call |
| POST `/v1/audio/cue` | JSON `kind`: listening, thinking, or paused | Selected-voice cached PCM16, mono 24 kHz |
| POST `/v1/chat/completions` | JSON `messages` with system/user/assistant roles | One assistant message; non-streaming |
| POST `/v1/audio/speech` | JSON `{"input":"Hello"}` | Raw signed little-endian PCM16, mono 24 kHz, <=60 seconds |

The `/v1` naming is a limited compatibility contract, not a complete implementation of any cloud API. Speech responses are raw PCM, not WAV; voice previews are WAV. Chat requests accept 1–16 messages of at most 8,000 characters each and use a configurable output limit (1200 by default, 128–4096 allowed).

## Device controls

The bridge recognizes supported volume and brightness phrases and returns metadata. Compatible firmware must apply limits, update hardware, persist settings, and confirm the resulting value. The prototype uses volume 0–100 and brightness 10–100. “Increase volume ten percent” means ten percentage points, not a proportional multiplication. Unsupported commands continue as ordinary chat. The new `firmware/Franky` implementation applies these actions and persists actual levels. LLM reply text is never interpreted as a hardware command.

## Limits

CPU speech recognition is serialized. Speech generation is serialized to protect the local model. This is a home prototype service, not a multi-user hosted platform. HTTP endpoints have no login or user accounts. There is no automatic Windows service installation, remote management, or Internet exposure configuration.

## Optional providers and credential separation

`provider` defaults to `lmstudio`. Cloud endpoints are fixed HTTPS URLs and requests do not follow redirects. Credentials come from provider-specific environment variables or Windows DPAPI files under ignored `bridge/.secrets`; they never enter firmware, config.json, browser responses, or release archives. OpenAI uses `/responses` with `store: false`; other adapters use their chat-completions interface. No provider or paid-model fallback exists.

## Robot execution

The main task handles the LCD, setup HTTP server, DNS, buttons, and persisted settings. One background task owns microphone/speaker access and blocking bridge requests. Bounded queues carry work and status/control results. Settings changes are rejected while a conversation is active. Microphone recordings and speech buffers use PSRAM, with explicit duration and response-size limits.

The listening-settings endpoint is an exception to idle-only writes: it can cancel capture during background listening or a question. Cancellation uses an atomic flag; only the audio task touches I2S. Pause persists in NVS. Background energy-gated utterances are bounded to four seconds, with pre-roll and trailing silence, and sent only to the local wake endpoint. Accepted wake phrases cause a ready cue, then a separate bounded question recording. Capture is half-duplex and suspended during recognition/playback. See [hands-free limitations](HANDS-FREE.md).
