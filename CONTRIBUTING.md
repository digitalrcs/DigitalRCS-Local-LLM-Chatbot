# Contributing

Small fixes, clearer instructions, and reproducible bug reports are welcome. Keep the beginner experience central. Do not add inherited firmware or fonts without documenting redistribution terms.

## Development checks

Create a Python 3.13 virtual environment and install `bridge/requirements-lock.txt`. From the project root:

```powershell
$env:PYTHONPATH = "bridge"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Unit tests use mocks and do not download speech models or require a robot. Integration checks require model downloads and a running LM Studio instance. Never describe mocked tests as hardware validation.

## Releases

Run `scripts/package.py` with Python from the project root. It packages an explicit source/documentation allowlist and generates a SHA-256 checksum in `dist/`. Inspect the ZIP and scan it for private data before publishing. Local settings, environments, models, logs, and firmware are excluded. Keep release notes explicit about the PC-only preview scope.

Open a pull request explaining the behavior change and how it was checked. For bugs include steps to reproduce and sanitized errors. Avoid formatting-only rewrites unrelated to your change.
