# Contributing

Small fixes, clearer instructions, and reproducible bug reports are welcome. Keep the beginner experience central. Do not add inherited firmware or fonts without documenting redistribution terms.

## Development checks

Create a Python 3.13 virtual environment and install `bridge/requirements-lock.txt`. From the project root:

```powershell
$env:PYTHONPATH = "bridge"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Unit tests use mocks and do not download speech models or require a robot. Integration checks require model downloads and a running LM Studio instance. Never describe mocked tests as hardware validation.

Run `node --test tests/ui_pages_test.cjs` with Node 22+ for settings synchronization, recovery, Stop, and readiness-page regressions. With a C++17 compiler (`g++`) on PATH, compile/run `tests/control_logic_test.cpp` and `tests/interaction_test.cpp`, then run `tests/audio_capture_test.py`, `tests/audio_playback_test.py`, and `tests/network_cancel_test.py` with Python. These use deterministic fake hardware; a firmware build and robot checks are still needed.

## Releases

Run `scripts/package.py` with Python from the project root. It packages an explicit source/documentation allowlist and generates a SHA-256 checksum in `dist/`. Inspect the ZIP and scan it for private data before publishing. Local settings, credentials, environments, models, logs, backups, and compiled firmware binaries are excluded. The new firmware source and original artwork are included. Keep release notes explicit about the development-preview scope and the distinction between source builds and precompiled firmware.

Open a pull request explaining the behavior change and how it was checked. For bugs include steps to reproduce and sanitized errors. Avoid formatting-only rewrites unrelated to your change.
