# Hello Franky, and microphone pause

With the updated PC bridge and firmware, Franky can answer without holding a button. This is an experimental local speech-recognition feature, not a claim of Google Home microphone range or a trained on-device wake-word model.

## Turn it on

1. Start the updated voice bridge and LM Studio as usual.
2. Open the device address shown on Franky's screen in your phone's browser.
3. Under **Hands-free conversations**, check **Enable Hello Franky** and choose **Save hands-free settings**.
4. Say **Hello Franky** on its own. Wait for **I'm listening**, then ask your question.
5. Pause briefly when finished. Franky ends the recording after about 0.8 seconds of quiet, or at the ten-second limit.

Before requesting the model's answer, Franky says **One moment, let me think**. This neutral acknowledgment does not promise that he can fulfill the request. Simple volume/brightness commands receive their normal confirmation instead. Short voice cues are cached on the PC for the selected voice; the first use can take longer.

Say the wake phrase separately from the question. Recognition pauses while the PC checks a snippet, while Franky answers, and briefly between recordings. He cannot hear an interruption while speaking. If he misses you, wait a moment and repeat **Hello Franky**. The BOOT hold-to-talk option remains available; during a wake check it may take several seconds to become available.

## Pause and resume

- While Franky is waiting, say **stop listening**, **pause listening**, or **go to sleep**. These also work as your question after waking him.
- Or choose **Pause listening** on his device page, including during background listening.
- The LCD shows **Listening paused**. The pause is saved and survives power cycling.
- **Press BOOT once to resume.** You can also choose **Resume listening** on the page. With hands-free disabled, the next BOOT hold starts a normal recording.

Pause stops microphone capture. A snippet already sent to the local PC may finish processing, but its result is discarded after cancellation. An answer or voice cue already playing may finish; this is microphone pause, not a speaker mute. Pressing BOOT while powering on still selects ESP32 download mode, so use BOOT only after Franky has started.

## Room noise and distance

Start nearby in a quiet room. The **microphone threshold** defaults to 120. Lower it toward 60 for quieter speech; raise it if background noise repeatedly starts recognition. This is an audio-energy threshold, not a guaranteed distance setting. TV speech can cause false activations. A deliberately spoken matching phrase is not authentication.

The local recognizer accepts Franky/Frankie spellings. It requires a standalone greeting and does not wake merely because the name occurs in another sentence. There is no guarantee against recognition errors. **Hello Franky** is the recommended phrase; **Hey Franky** is also accepted when recognized correctly.

## Where the sound goes

Hands-free is off by default on fresh installations. When enabled and not paused, the kit samples room audio and sends speech-like snippets to the bridge PC for local Whisper recognition. Background snippets do not go to LM Studio or cloud chat providers, and their transcripts are not returned to the device or intentionally stored. After a successful wake, your question goes through your selected provider as usual. Optional cloud providers receive the question text.

This mode uses more PC processing and LAN traffic than button mode. Keep the bridge PC awake. A lost connection means wake recognition is unavailable. Use only a trusted home network.
