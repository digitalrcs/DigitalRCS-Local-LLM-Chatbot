"""Prepare public speech/flash assets for the Windows installer; never copy configuration."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/installer-assets"
KOKORO = {
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}
WHISPER = {"base.en": "3d3d5dee26484f91867d81cb899cfcf72b96be6c", "tiny.en": "0d3d19a32d3338f10357c0889762bd8d64bbdeba"}
ESPTOOL_URL = "https://github.com/espressif/esptool/releases/download/v5.2.0/esptool-v5.2.0-windows-amd64.zip"
ESPTOOL_SHA = "ef0522120afb5e8e673d68726c32e0de416990fc62dc313191721edeb0a74fc6"
# These manually collected source packages are separate from regenerated model/tool records.
CURATED_SOURCE_ARCHIVES = {
    "av-18.1.0.tar.gz",
    "PyAV-18.1.0-build-source.zip",
    "pyav-ffmpeg-8.1.2-1-build-source.zip",
    "pyav-ffmpeg-8.1.2-1-dependency-sources.zip",
    "pyav-msys2-runtime-sources.zip",
    "Franky-0.4.0-firmware-relink-sources.zip",
    "Franky-0.4.0-sdk-notices.zip",
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path, expected=None):
    if path.is_file() and (expected is None or sha(path) == expected):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=(15, 90)) as response:
        response.raise_for_status()
        with partial.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
    if expected and sha(partial) != expected:
        raise ValueError("Downloaded asset hash differs: " + path.name)
    partial.replace(path)


def preserved_source_assets(directory):
    """Keep verified curated sources; never carry forward model/tool metadata."""
    manifest = directory / "assets.json"
    if not manifest.is_file():
        return []
    previous = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(previous, dict) or not isinstance(previous.get("assets"), list):
        raise ValueError("Existing assets.json must contain an assets list")
    retained, seen = [], set()
    for record in previous["assets"]:
        if not isinstance(record, dict) or record.get("name") not in CURATED_SOURCE_ARCHIVES:
            continue
        name = record["name"]
        if name in seen:
            raise ValueError("Duplicate curated source record: " + name)
        seen.add(name)
        digest = record.get("sha256", "")
        archive = directory / name
        if (not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)
                or not archive.is_file() or sha(archive) != digest.lower()):
            raise ValueError("Curated source archive is missing or changed: " + name)
        retained.append(record)
    return retained


def main():
    from faster_whisper.utils import download_model
    OUT.mkdir(parents=True, exist_ok=True)
    retained_sources = preserved_source_assets(OUT)
    assets = []
    for name, digest in KOKORO.items():
        target = OUT / "models/kokoro" / name
        cached = ROOT / "bridge/models/kokoro" / name
        url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/" + name
        if not target.is_file() and cached.is_file() and sha(cached) == digest:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, target)
        download(url, target, digest)
        assets.append({"name": name, "url": url, "sha256": digest, "license": "Apache-2.0 (model); see bundled model notices"})
        print("Verified " + name, flush=True)
    for name, revision in WHISPER.items():
        target = OUT / "models" / ("whisper-" + name)
        download_model(name, output_dir=str(target), cache_dir=str(ROOT / "bridge/models"), revision=revision, use_auth_token=False)
        # The model payload is self-contained; do not ship Hub lock/download state.
        files = [{"name": p.name, "sha256": sha(p)} for p in sorted(target.iterdir()) if p.is_file()]
        assets.append({"name": "whisper-" + name, "url": "https://huggingface.co/Systran/faster-whisper-" + name, "revision": revision, "license": "MIT", "files": files})
        print("Prepared listening model " + name, flush=True)
    archive = OUT / "esptool-v5.2.0-windows-amd64.zip"
    download(ESPTOOL_URL, archive, ESPTOOL_SHA)
    with zipfile.ZipFile(archive) as source:
        candidates = [n for n in source.namelist() if n.endswith('/esptool.exe') or n == 'esptool.exe']
        if len(candidates) != 1:
            raise ValueError("Unexpected esptool package layout")
        target = OUT / "esptool.exe"
        target.write_bytes(source.read(candidates[0]))
    assets.append({"name": "esptool.exe", "version": "5.2.0", "url": ESPTOOL_URL, "archive_sha256": ESPTOOL_SHA, "sha256": sha(target), "license": "GPL-2.0-or-later"})
    download("https://aka.ms/vc14/vc_redist.x64.exe", OUT / "vc_redist.x64.exe")
    assets.append({"name": "vc_redist.x64.exe", "url": "https://aka.ms/vc14/vc_redist.x64.exe", "sha256": sha(OUT / "vc_redist.x64.exe"), "license": "Microsoft redistribution terms; vendor-signed installer"})
    notices = OUT / "notices"
    notices.mkdir(exist_ok=True)
    urls = {
        "WHISPER-LICENSE.txt": "https://raw.githubusercontent.com/openai/whisper/main/LICENSE",
        "KOKORO-MODEL-CARD.md": "https://huggingface.co/hexgrad/Kokoro-82M/raw/main/README.md",
        "APACHE-2.0.txt": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "KOKORO-ONNX-LICENSE.txt": "https://raw.githubusercontent.com/thewh1teagle/kokoro-onnx/main/LICENSE",
        "ESPTOOL-LICENSE.txt": "https://raw.githubusercontent.com/espressif/esptool/v5.2.0/LICENSE",
    }
    for name, url in urls.items():
        download(url, notices / name)
    download("https://github.com/espressif/esptool/archive/refs/tags/v5.2.0.zip", OUT / "esptool-5.2.0-source.zip")
    assets.append({"name": "esptool-5.2.0-source.zip", "url": "https://github.com/espressif/esptool/archive/refs/tags/v5.2.0.zip", "sha256": sha(OUT / "esptool-5.2.0-source.zip")})
    for name, url in {
        "espeak-ng-1.52.0-source.zip": "https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.zip",
        "espeakng-loader-source.zip": "https://github.com/thewh1teagle/espeakng-loader/archive/e5e9200dc3fd894b7415942c2602fc31526d60fc.zip",
    }.items():
        download(url, OUT / name)
        assets.append({"name": name, "url": url, "sha256": sha(OUT / name)})
    assets.extend(retained_sources)
    manifest = OUT / "assets.json"
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"assets": assets}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest)
    print("Asset manifest ready: " + str(OUT / "assets.json"))


if __name__ == "__main__":
    main()
