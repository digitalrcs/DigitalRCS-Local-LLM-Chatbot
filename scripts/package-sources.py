"""Package the installer's verified source/notices materials for its release page."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "dist/installer-assets"
PAYLOAD = ROOT / "dist/installer/payload"
VERSION = runpy.run_path(str(ROOT / "scripts/package.py"))["VERSION"]
REQUIRED = runpy.run_path(str(ROOT / "scripts/prepare-installer-assets.py"))["CURATED_SOURCE_ARCHIVES"] | {
    "esptool-5.2.0-source.zip", "espeak-ng-1.52.0-source.zip", "espeakng-loader-source.zip"
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    manifest = json.loads((ASSETS / "assets.json").read_text(encoding="utf-8"))
    inputs = {}
    records = {}
    for entry in manifest["assets"]:
        name = entry["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.(zip|tar\.gz|tgz)", name):
            continue
        if name in records:
            raise ValueError("Duplicate source archive: " + name)
        source = ASSETS / name
        if not source.is_file() or source.is_symlink() or digest(source) != entry["sha256"]:
            raise ValueError("Missing or changed source archive: " + name)
        records[name] = entry
        inputs["archives/" + name] = source
    if REQUIRED - records.keys():
        raise ValueError("Required source material missing: " + ", ".join(sorted(REQUIRED - records.keys())))
    for source in sorted((ASSETS / "notices").iterdir()):
        if source.is_file():
            inputs["notices/" + source.name] = source
    inputs["assets.json"] = ASSETS / "assets.json"
    inputs["firmware/manifest.json"] = ASSETS / "firmware/manifest.json"
    inputs["installer-assets-manifest.json"] = PAYLOAD / "installer/assets-manifest.json"
    inputs["runtime-notices/LICENSE.txt"] = PAYLOAD / ".runtime/LICENSE.txt"
    for source in sorted((PAYLOAD / ".runtime/Lib/site-packages").rglob("*")):
        relative = source.relative_to(PAYLOAD / ".runtime/Lib/site-packages")
        if (source.is_file() and ".dist-info" in relative.parts[0]
                and ("licenses" in relative.parts or re.match(r"^(LICENSE|COPYING|NOTICE|AUTHORS)", source.name, re.I))):
            inputs["python-package-notices/" + relative.as_posix()] = source

    readme = f"""# Franky {VERSION}: bundled sources and notices

Normal Windows users only need Setup.exe. This companion is for people inspecting,
rebuilding, or modifying the bundled components. It contains no voice models,
installed Python environment, provider keys, recordings, or device backups.

## Contents

- `archives/`: matching upstream source packages/build scripts and the Franky
  firmware source/relink companion. Each archive has its own instructions/notices.
- `notices/`, `runtime-notices/`, `python-package-notices/`: retained license texts.
- `assets.json`: source/model/tool provenance and hashes.
- `installer-assets-manifest.json`: runtime and Python wheel versions/URLs/hashes.
- `firmware/manifest.json`: reference firmware image identities; no device data.
- `SHA256SUMS.txt`: hashes of this companion's material files.

The project's MIT license does not replace third-party licenses. The firmware
relink archive explains how to rebuild with a replacement Arduino core; its pinned
SDK and compiler are separately installed prerequisites. The SDK notice archive
provides linked-component notices and upstream source references. PyAV/FFmpeg,
MSYS2 runtime, eSpeak, and esptool materials retain their component terms.

## Reuse as installer build inputs

Start with the matching Franky source checkout. Copy the files from `archives/`
into `dist/installer-assets`, copy `notices/` to that directory's `notices/`, and
copy this `assets.json` there. Then run `scripts/prepare-installer-assets.py` to
prepare the public model/tool inputs while retaining verified source records.
Do not combine a different binary version with these source records.

Supply the matching four firmware images and their manifest separately. They are
under `installer/firmware` in the installed release; alternatively rebuild them
from the pinned firmware sources and record the new hashes. Read
`docs/BUILD-INSTALLER.md` in the main project before building a release.
"""
    output = ROOT / "dist" / f"DigitalRCS-Franky-{VERSION}-Bundled-Sources.zip"
    temporary = output.with_suffix(".zip.part")
    checksums = []
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        archive.writestr("README.md", readme)
        for name, source in sorted(inputs.items()):
            if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(ROOT / "dist"):
                raise ValueError("Unexpected source input: " + name)
            checksums.append(digest(source) + "  " + name)
            archive.write(source, name)
        archive.writestr("SHA256SUMS.txt", "\n".join(checksums) + "\n")
    temporary.replace(output)
    output.with_suffix(output.suffix + ".sha256").write_text(digest(output) + "  " + output.name + "\n", encoding="ascii")
    print(f"Created {output.name}: {output.stat().st_size} bytes, {len(inputs)} material files")


if __name__ == "__main__":
    main()
