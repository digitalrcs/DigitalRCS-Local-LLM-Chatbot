# Changelog

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
