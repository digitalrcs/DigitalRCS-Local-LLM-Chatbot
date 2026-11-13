# Contributing

Small fixes, clearer instructions, and reproducible bug reports are welcome. Keep the beginner experience central. Do not add inherited firmware or fonts without documenting redistribution terms.

## Development checks

Create a Python 3.13 virtual environment and install `bridge/requirements-lock.txt`. From the project root:

```powershell
$env:PYTHONPATH = "bridge"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Unit tests use mocks and do not download speech models or require a robot. Integration checks require model downloads and a running LM Studio instance. Never describe mocked tests as hardware validation.

Run `node --test tests/ui_pages_test.cjs` with Node 22+ for settings synchronization, recovery, Stop, and readiness-page regressions. With a C++17 compiler (`g++`) on PATH, compile/run `tests/control_logic_test.cpp` and `tests/interaction_test.cpp`, then run `tests/audio_capture_test.py`, `tests/audio_playback_test.py`, `tests/network_cancel_test.py`, and `tests/frame_reader_test.py` with Python. These use deterministic fake hardware; a firmware build and robot checks are still needed.

The Windows `installer-ui` CI job compiles `installer/FrankySetup.cs` with the built-in .NET Framework compiler and runs `tests/installer_ui_test.cs`. These tests check navigation, completion status, stale settings, busy controls, and explicit USB confirmation without starting services or flashing hardware. Use the exact compile commands in `.github/workflows/tests.yml` to run them locally.

For documentation changes, use the exact button names from the app. Explain a new term the first time a beginner needs it. Keep the Setup.exe path separate from the manual Python/command-window path. Check relative links and any section anchors you change.

## Releases

There are two packages. **Setup.exe** is the beginner download; build it with [BUILD-INSTALLER.md](docs/BUILD-INSTALLER.md). It includes a private runtime, speech files, and the tested optional firmware. Keep matching component notices/source and firmware relink materials with the binaries, provenance and checksums. Publish those materials as **Bundled-Sources.zip** as well as keeping them inside the installer.

The **Windows source ZIP** is built by running `scripts/package.py` with Python from the project root. It packages an explicit source/documentation allowlist and generates a SHA-256 checksum in `dist/`. Local settings, credentials, environments, models, logs, backups, and compiled firmware are excluded from this ZIP. Newly written firmware source and artwork are included.

Inspect both packages for private data before publication. Update the README download link, setup guide, changelog, release notes, and documentation index together. Release notes should say which file beginners should download, which checks passed, and which installation/hardware checks remain unverified. Use a prerelease tag while this is a development preview; do not claim every Windows PC or robot was tested.

Open a pull request explaining the behavior change and how it was checked. For bugs include steps to reproduce and sanitized errors. Avoid formatting-only rewrites unrelated to your change.
