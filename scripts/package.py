"""Build a source-only release from an explicit allowlist; never include local state."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0-preview.1"
FILES = [
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md",
    "START-HERE.cmd", "START-FRANKY.cmd", "CHECK-SETUP.cmd",
    "bridge/server.py", "bridge/settings.py", "bridge/configure.py", "bridge/config.example.json",
    "bridge/neural_voice.py", "bridge/voice_settings.py", "bridge/device_commands.py",
    "bridge/download_voice.py", "bridge/speak.ps1", "bridge/voices.html",
    "bridge/requirements.txt", "bridge/requirements-lock.txt",
    "scripts/setup.ps1", "scripts/start.ps1", "scripts/check.ps1", "scripts/allow-lan.ps1", "scripts/package.py",
    "docs/INSTALL.md", "docs/TROUBLESHOOTING.md", "docs/ARCHITECTURE.md",
    "tests/test_bridge.py", "tests/test_neural_voice.py", "tests/test_voice_settings.py",
    "tests/test_device_commands.py", "tests/test_settings.py", "tests/test_providers.py", "tests/control_logic_test.cpp",
    "bridge/provider_config.py", "bridge/credential_store.py", "bridge/providers.py",
    "CHANGE-PROVIDER.cmd", "BUILD-FRANKY.cmd", "FLASH-FRANKY.cmd",
    "scripts/provider.ps1", "scripts/build-firmware.ps1", "scripts/flash-firmware.ps1", "scripts/flash-wizard.ps1",
    "scripts/generate_frog.py", "scripts/embed_setup.py", "docs/PROVIDERS.md", "docs/FIRMWARE.md",
]

# Only the public firmware source/artwork directories; never build outputs or flash backups.
for directory in (ROOT / "firmware", ROOT / "docs/images"):
    for source in sorted(directory.rglob("*")):
        if source.is_file() and (source.suffix in {".ino", ".h", ".c", ".json", ".md", ".html", ".svg", ".png"} or source.name == "LICENSE"):
            FILES.append(source.relative_to(ROOT).as_posix())

def main():
    target = ROOT / "dist"
    target.mkdir(exist_ok=True)
    name = f"DigitalRCS-Local-LLM-Chatbot-{VERSION}-Windows"
    archive = target / (name + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for relative in FILES:
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(relative)
            output.write(source, name + "/" + relative)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (target / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Created {archive.name}: {archive.stat().st_size} bytes, {len(FILES)} files")

if __name__ == "__main__":
    main()
