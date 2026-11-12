// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
// Types used by the voice worker in Franky.ino. They live in a header because
// the Arduino builder places generated function prototypes above the .ino's
// own type definitions.

// The previous question and answer, sent with the next question for context.
struct History { String user,reply; };
// Result of one question: finished (already reported), speak `answer`, or
// fall back to step-by-step requests for an older bridge.
enum class Turn { Finished, Speak, Unsupported };
// One chime fetched from the bridge and kept in PSRAM.
struct CachedCue { const char* kind; uint8_t* data; size_t bytes; };
