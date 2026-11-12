# Changelog

## 0.4.0-preview.1

Faster, smoother conversations and a talking mouth. Update and restart the bridge, then build and flash the firmware. Older firmware keeps working with the new bridge, and the new firmware falls back to the old requests with an older bridge.

- **Streamed replies.** New `POST /v1/converse` takes the recording and returns one stream: what was heard, the thinking chime, then each sentence's speech as soon as it is ready. A chat thread turns streamed model text into sentences while a voice thread speaks them, so Franky starts talking after the first sentence instead of after the whole reply. The robot plays audio as it downloads, which also removes the 60-second reply buffer.
- **Reasoning off for voice.** New `disable_thinking` setting (default `true`) adds `/no_think` for Qwen3-family models. Reasoning text is also removed from streamed replies.
- **Reasoning-aware reply budget.** `max_output_tokens` defaults to 1200; explicit saved values are kept. Gemma can spend a 256-token budget on reasoning before returning an answer. Output-limit failures are reported instead of treating incomplete text as a finished reply.
- **Wake checks no longer delay questions.** Wake phrases use their own `tiny.en` model and lock (`WAKE_WHISPER_MODEL`). If it cannot load, wake checks fall back to the question model. `WHISPER_DEVICE=cuda` optionally moves recognition to a GPU.
- **Chimes are cached on the robot** after the first download.
- **Talking mouth.** While speaking, the frog's mouth opens to one of four sizes from the loudness of the audio.
- **Timing logs.** The bridge log shows the time for speech recognition, wake checks, first speech and the full reply.
- Stream cancellation is tied to the HTTP response, including disconnects. Heartbeats keep the robot connected while waiting for model or voice work; partial failures remain errors and do not update conversation history.
- Streamed provider text is decoded as UTF-8; frame byte limits cover Unicode metadata and replies. Firmware propagates playback failures during waits and avoids an Arduino helper-name collision.

## 0.3.3-preview.3

- Expanded Windows setup and AI-server instructions with recovery for unfinished Kokoro `.part` downloads, the exact retry command, the X64 C++ runtime prerequisite, eSpeak troubleshooting, and required voice-preview verification. Documentation update; bridge and firmware behavior are unchanged.

## 0.3.3-preview.2

- Replaced the spoken thinking acknowledgment with the short ready chime after a question. Update and restart the voice bridge; existing firmware needs no reflash.

## 0.3.3-preview.1

- Web settings and Talk remain usable during passive hands-free monitoring.
- Partial settings saves and synchronized controls preserve spoken changes and unsaved edits; the page recovers after an initial connection failure.
- BOOT during an active interaction and the new web Stop button cancel capture, playback, pending replies, and follow-ups. Response waits are cancellable; network connection/upload operations may still take time to return.
- The voice page shows cached recognition, voice, and chat readiness while speech models load in the background. Availability checks do not generate answers or speech.
- Cancelling provider setup no longer reports success or continues model downloads.
- Windows AI-server migration guide and SET-BRIDGE-ADDRESS launcher; the dashboard identifies the robot-facing bridge address separately from LM Studio's address.
- Added browser-script, interaction-state, playback, network cancellation, setup, and readiness regression checks.

## 0.3.2-preview.1

- Standalone thank-you phrases end the conversation and return to wake-word mode without pausing.
- Stronger, longer follow-up chime with playback failure reporting.
- Button-started questions also offer follow-ups when hands-free mode is enabled.

## 0.3.1-preview.1

- Fifteen-second listening and follow-up windows; longer pauses within questions.
- Shorter gaps between wake checks and quiet return to wake mode after silence.
- Original rising ready and falling pause chimes, generated locally.
- Deterministic capture timing, buffer-limit, cancellation, and chime tests.

## 0.3.0-preview.1

- Optional local Hello Franky recognition, automatic question recording, and spoken thinking acknowledgment.
- Persistent microphone pause by voice or web control; BOOT resumes listening.
- Configurable microphone threshold, selected-voice cue cache, and wake/pause boundary tests.
- Background snippets stay on the local bridge; hands-free is disabled on fresh installations.

## 0.2.0-preview.1

- New independent Franky firmware source, original animated frog artwork, setup page, and build/flash scripts.
- Liam is now the default voice; LM Studio remains the default AI provider.
- Optional OpenAI Responses API, OpenRouter free models, and Gemini adapters.
- Local protected key entry, explicit provider selection, and no automatic paid fallback.
- Native control/URL tests, provider-contract tests, and expanded beginner guides.

Cloud generation requires user credentials; mocked adapter tests are not live-provider verification. Firmware is a development preview, with provenance recorded separately from the earlier adaptation.

## 0.1.0-preview.1

Initial public PC voice bridge preview for DigitalRCS Local LLM Chatbot.

- English recognition, LM Studio chat, and local Kokoro speech.
- Eleven male voices with preview and persistent selection.
- Guided Windows setup, start launcher, and connection check.
- Deterministic volume/brightness command metadata for compatible clients.
- Beginner installation guide, troubleshooting, API notes, and explicit credits.

Robot firmware, flashing tools, factory backups, personal configuration, and model files are not included. This is not yet a complete installable replacement for a factory LAFVIN chatbot.
