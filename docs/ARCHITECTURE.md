# Architecture and API

The included Python FastAPI bridge connects a compatible audio client to faster-whisper (English recognition), LM Studio by default (chat), and Kokoro (speech). All model inference can run locally after downloads. Optional OpenAI, OpenRouter free-model, and Gemini adapters are selected explicitly on the PC; see [PROVIDERS.md](PROVIDERS.md). Device controls are parsed using explicit rules; model replies are not executed as hardware commands.

## Configuration

The wizard writes `bridge/config.json`, which Git and the release builder exclude. `LM_STUDIO_URL` and `LM_STUDIO_MODEL` environment variables override that file. `LM_STUDIO_TOKEN` optionally supplies authentication to LM Studio. Restart the bridge after changes. The default server address is `http://127.0.0.1:1234/v1`; no chat model is selected until setup.

`WHISPER_MODEL` defaults to `base.en` for questions. `WAKE_WHISPER_MODEL` defaults to `tiny.en` for hands-free wake checks; set it to the same name as `WHISPER_MODEL` to share one model. Separate models have separate locks; when the wake model cannot load, wake checks share the question model and its lock. `WHISPER_DEVICE` defaults to `cpu` (keeps the GPU free for the chat model); `cuda` uses a GPU. `TTS_ENGINE` defaults to `kokoro`; `windows` selects the optional Windows SAPI fallback. The voice picker requires Kokoro. Voice choice persists in ignored `bridge/voice_settings.json`. Models live in ignored `bridge/models/`.

`public_bridge_url` optionally records the robot-facing LAN address displayed in the dashboard; **SET-BRIDGE-ADDRESS.cmd** edits it without changing provider configuration. `BRIDGE_PUBLIC_URL` overrides the stored value. This is an advertised HTTP IPv4/DNS origin on port 8766, not a bind address or automatic device reconfiguration. The bridge and its website share the same process and port. See [Windows AI-server migration](WINDOWS-SERVER.md).

## Endpoints

| Route | Request | Response |
| --- | --- | --- |
| GET `/health` | None | Service status and configured model details; not an upstream readiness probe |
| GET `/ready` | None | Cached readiness: overall `starting`, `ready`, or `degraded`, plus recognition, voice, and chat checks with status/message; always HTTP 200 |
| GET `/` | None | Voice picker |
| GET `/voices` | None | Voice catalog and selected ID |
| POST `/voice` | JSON `{"voice":"am_liam"}` | Persisted selection |
| POST `/voice/preview` | Same voice JSON | Playable WAV preview; does not save selection |
| POST `/v1/audio/transcriptions` | Multipart `file`: mono 16-bit 16 kHz WAV, <=13 seconds and <=500 KB | `text` and optional deterministic `control` metadata |
| POST `/v1/audio/wake` | Same local WAV contract | Boolean `wake` and `pause` flags only; no transcript or provider call |
| POST `/v1/audio/cue` | JSON `kind`: listening, followup, thinking, paused, or welcome | PCM16, mono 24 kHz: synthesized bell cues, or selected-voice cached speech for welcome |
| POST `/v1/converse` | Multipart `file` (same WAV contract) and optional `messages`: JSON list of system/assistant/user messages (at most 15) | Streamed frames; see [Streamed conversation](#streamed-conversation) |
| POST `/v1/chat/completions` | JSON `messages` with system/user/assistant roles | One assistant message; non-streaming |
| POST `/v1/audio/speech` | JSON `{"input":"Hello"}` | Raw signed little-endian PCM16, mono 24 kHz, <=60 seconds |

The `/v1` naming is a limited compatibility contract, not a complete implementation of any cloud API. Speech responses are raw PCM, not WAV; voice previews are WAV. Chat requests accept 1–16 messages of at most 8,000 characters each and use a configurable output limit (`max_output_tokens`, 1200 by default, 128–4096 allowed). This includes reasoning tokens; existing configured limits are preserved. `disable_thinking` (default `true`) appends `/no_think` for Qwen3-family templates that support it; Gemma and other models are not changed. Reasoning wrapped in `<think>` tags and separate streamed reasoning fields are excluded from spoken replies. Provider SSE is always decoded as UTF-8, and a stream must end with a completion marker or successful finish reason.

## Streamed conversation

`/v1/converse` replaces the separate transcription, chat and speech requests for one question. The bridge transcribes the recording, then streams the answer while the model is still writing it:

1. A chat thread reads the provider's streamed text (`stream: true`), removes reasoning, and splits it into sentences.
2. A voice thread turns each sentence into speech with the same engine as `/v1/audio/speech`.
3. The response sends each sentence as soon as its speech is ready.

The response is a byte stream of frames: 1 byte type, 4-byte little-endian length, then the payload. Clients should use HTTP/1.0 so the stream is not chunked.

| Type | Payload |
| --- | --- |
| `J` | JSON: `text`, `control`, `pause`, `end_conversation` (same as `/v1/audio/transcriptions`) |
| `C` | Cue PCM16 mono 24 kHz: the thinking chime, or the pause chime |
| `T` | UTF-8 text of the sentence the next `P` frame speaks |
| `P` | Speech PCM16 mono 24 kHz |
| `H` | Empty heartbeat while waiting for speech; resets the client's idle timeout |
| `E` | JSON end: `{"reply": text}`, `{"error": message}` with optional `partial_reply`, or `{}` when no chat was needed |

Pause and thank-you phrases and device commands never reach the chat provider. For a device command the stream ends after `J` and the robot speaks its own confirmation. Spoken replies stop at 1,800 characters including joining spaces. JSON is UTF-8 without ASCII escaping, and each `J`/`T`/`E` payload is limited to 8,192 encoded bytes. Errors before streaming starts return normal HTTP status codes; later errors arrive in `E`, including failures after some audio has played. Failed turns are not saved as successful history and do not open follow-up listening.

Disconnects signal a shared cancellation event through the HTTP response lifecycle. Queue waits are bounded and cancellation-aware; heartbeats prevent slow generation plus synthesis from exhausting the robot's 60-second no-data timeout. Provider streaming checks cancellation on every SSE line, including reasoning-only events. A provider that stops sending data can still take up to its read timeout to release its request, and in-progress speech synthesis must finish its current call. Firmware 0.4 uses this endpoint and falls back to the separate requests when a bridge answers 404.

The bridge log reports `Franky timing:` lines for speech recognition, wake checks, first speech and the full reply.

On bridge startup, independent background workers load the local speech models under the same locks used by inference, so the dashboard remains available during preparation. These checks do not generate speech or chat. The selected provider's model listing is checked with short connection/read timeouts and refreshed no more than once every 30 seconds; failed speech loads also retry after 30 seconds. `/ready` reads cached results only, so browser polling never creates extra provider requests. A listed model does not prove inference access, quota, speed, or microphone/speaker quality. Windows speech reports configuration availability rather than a completed voice test.

## Device controls

The bridge recognizes supported volume and brightness phrases and returns metadata. Compatible firmware must apply limits, update hardware, persist settings, and confirm the resulting value. The prototype uses volume 0–100 and brightness 10–100. “Increase volume ten percent” means ten percentage points, not a proportional multiplication. Unsupported commands continue as ordinary chat. The new `firmware/Franky` implementation applies these actions and persists actual levels. LLM reply text is never interpreted as a hardware command.

## Limits

Question recognition and wake recognition are each serialized. Speech generation is serialized to protect the local model. This is a home prototype service, not a multi-user hosted platform. HTTP endpoints have no login or user accounts. There is no automatic Windows service installation, remote management, or Internet exposure configuration.

## Optional providers and credential separation

`provider` defaults to `lmstudio`. Cloud endpoints are fixed HTTPS URLs and requests do not follow redirects. Credentials come from provider-specific environment variables or Windows DPAPI files under ignored `bridge/.secrets`; they never enter firmware, config.json, browser responses, or release archives. OpenAI uses `/responses` with `store: false`; other adapters use their chat-completions interface. No provider or paid-model fallback exists.

## Robot execution

The main task handles the LCD, setup HTTP server, DNS, buttons, and persisted settings. One background task owns microphone/speaker access and blocking bridge requests. Bounded queues carry work and status/control results. Settings changes are rejected while a conversation is active. Microphone recordings and speech buffers use PSRAM, with explicit duration and response-size limits. Streamed replies are played as they arrive in 1 KB pieces; between sentences the speaker receives silence. Chimes are fetched once and cached in PSRAM. While speaking, the playback loop publishes a mouth level (0–3) from the audio loudness through an atomic value, and the display loop draws the frog's mouth from it about 16 times a second.

Passive wake monitoring remains available to web controls: a settings write cancels the background worker, and web Talk queues one recording after it completes. Active conversation writes remain rejected. `POST /controls` accepts one or both of `volume`/`brightness`; `POST /listening` accepts any of `enabled`/`paused`/`threshold`. Existing full payloads remain supported. `/status` retains worker `busy` and `wake_monitoring` flags and adds `stopping`, `pending_manual`, and `follow_up_pending` so Stop also works between queued actions.

`POST /stop` (empty JSON, normal device-page token) and BOOT during active work cancel capture, playback, pending manual jobs, and follow-ups without persisting pause. Listening pause also cancels current work and persists in NVS. Cancellation uses an atomic flag; only the audio worker touches I2S and its HTTP socket. HTTP response polling and reads observe cancellation, while DNS/connect and individual socket writes retain platform blocking limits. Cancelled queued events cannot change settings or reopen a follow-up. The bridge/provider may still finish a request that it already received.

Background energy-gated utterances are bounded to four seconds, with pre-roll and trailing silence, and sent only to the local wake endpoint. Accepted wake phrases cause a ready cue, then a separate bounded question recording. Capture is half-duplex and suspended during recognition/playback. See [hands-free limitations](HANDS-FREE.md).

Question and follow-up capture waits about 15 seconds for speech and uses 1.5 seconds of trailing silence. After a successful hands-free reply, another ready chime opens a follow-up window; silence returns to wake monitoring without a model call. Wake capture retains an 800 ms tail. Normal idle wake retries wait 40 ms rather than 700 ms, with a longer error backoff. Listening, follow-up, thinking, and pause cues use original PCM bell synthesis; thinking reuses the listening chime. The welcome cue remains cached local speech in the selected voice.
