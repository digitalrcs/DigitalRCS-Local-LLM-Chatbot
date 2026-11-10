"""Original soft bell cues, generated locally; no sampled commercial sounds."""
import numpy as np


def chime(kind: str) -> bytes:
    if kind not in {'listening', 'followup', 'paused'}:
        raise ValueError('Unknown chime')
    rate = 24000
    frequencies = (523.25, 392.00, 261.63) if kind == 'paused' else (523.25, 783.99, 1046.50)
    followup = kind == 'followup'
    tail, spacing = (.48, .15) if followup else (.38, .105)
    audio = np.zeros(int(rate * (.82 if followup else .62)), dtype=np.float64)
    t = np.arange(int(rate * tail)) / rate
    envelope = (1 - np.exp(-t / .006)) * np.exp(-t / (.12 if followup else .080))
    envelope *= np.minimum(1, (tail - t) / .025)
    for index, frequency in enumerate(frequencies):
        # A soft fundamental with light bell partials and overlapping tails.
        tone = (np.sin(2 * np.pi * frequency * t)
                + .16 * np.sin(2 * np.pi * frequency * 2.01 * t)
                + .05 * np.sin(2 * np.pi * frequency * 3.98 * t))
        offset = int(index * spacing * rate)
        gain = .42 if followup else (.22 if kind == 'listening' else .17)
        audio[offset:offset + len(t)] += tone * envelope * gain
    return (np.clip(audio, -.5, .5) * 32767).astype('<i2').tobytes()
