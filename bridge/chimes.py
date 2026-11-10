"""Original soft bell cues, generated locally; no sampled commercial sounds."""
import numpy as np


def chime(kind: str) -> bytes:
    if kind not in {'listening', 'paused'}:
        raise ValueError('Unknown chime')
    rate = 24000
    frequencies = (523.25, 783.99, 1046.50) if kind == 'listening' else (523.25, 392.00, 261.63)
    audio = np.zeros(int(rate * .62), dtype=np.float64)
    t = np.arange(int(rate * .38)) / rate
    envelope = (1 - np.exp(-t / .006)) * np.exp(-t / .080)
    envelope *= np.minimum(1, (.38 - t) / .025)
    for index, frequency in enumerate(frequencies):
        # A soft fundamental with light bell partials and overlapping tails.
        tone = (np.sin(2 * np.pi * frequency * t)
                + .16 * np.sin(2 * np.pi * frequency * 2.01 * t)
                + .05 * np.sin(2 * np.pi * frequency * 3.98 * t))
        offset = int(index * .105 * rate)
        audio[offset:offset + len(t)] += tone * envelope * (.22 if kind == 'listening' else .17)
    return (np.clip(audio, -.35, .35) * 32767).astype('<i2').tobytes()
