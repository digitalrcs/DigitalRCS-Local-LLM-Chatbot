# Build the Windows installer

This guide is for maintainers working on the code. To use Franky, download Setup.exe and follow [easy Windows setup](WINDOWS-INSTALLER.md).

## Build tools

Use Windows x64 with:

- Python **3.13 x64** and `bridge/requirements-lock.txt`, normally in the project's `.venv`.
- The Windows .NET Framework C# compiler, normally `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`.
- [Inno Setup 6](https://jrsoftware.org/isinfo.php).
- The tested LA064 firmware images and matching source/relink materials.

The builder does not copy the developer's virtual environment. It extracts the pinned **CPython 3.13.18** Windows x64 runtime from Astral's python-build-standalone distribution and installs the locked packages freshly into it. It does not change system Python.

## Prepare the inputs

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe scripts/prepare-installer-assets.py
```

This prepares public Kokoro and English Whisper models, standalone esptool, Microsoft's runtime installer, and component notices under ignored `dist/installer-assets`. Completed downloads are reused. Curated source records are preserved only when their archive hashes match; a changed or missing retained archive stops preparation. After copying source materials as described below, run the preparation command again so the final manifest includes both sets of inputs.

For a release build, also supply the matching third-party source materials from that release's **Bundled-Sources.zip**. Its README explains the folder layout. That companion contains upstream source archives, notices, provenance, and the firmware source/relink archive. Source collection is a maintainer task; the asset downloader does not reconstruct every upstream binary's full source bundle automatically.

Place the tested firmware's four separate images and `manifest.json` in `dist/installer-assets/firmware`. The manifest contains `chip: "esp32s3"`, `flash_size: "16MB"`, the firmware version/source commit, and file names, offsets and SHA-256 values:

| Offset | Image |
| --- | --- |
| `0x0` | Bootloader |
| `0x8000` | Partition table |
| `0xe000` | `boot_app0.bin`, exactly 8,192 bytes |
| `0x10000` | Franky application |

Do not use a merged flash dump. Keep private device backups, Wi-Fi settings and credentials out of these inputs. The v0.5.0-preview.1 installer uses the already-tested **0.4.0-dev** firmware. Its matching source/relink companion records the pinned SDK/compiler prerequisites and rebuild instructions. See [firmware development](FIRMWARE.md).

## Build

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-installer.ps1
```

The script stages files under `dist/installer/payload` and creates Setup.exe plus its checksum under `dist/installer/output`. It uses the explicit source-package allowlist and checks runtime, model, tool, and firmware hashes. It checks Microsoft's signature before packaging its prerequisite. Package license files stay in place, and component source/notices materials are copied into `third-party`.

The normal build replaces only its fixed staging payload. Do not use that staging folder as a running installation or save settings there.

After a successful full build, **`-SkipPayloadBuild`** reuses the staged runtime while recompiling the wizard and refreshing source/assets. It rejects unlisted or private files. Use a full build when changing Python dependencies. Optional parameters supply paths for the runtime archive, assets, firmware, compiler, and output; see `scripts/build-installer.ps1`.

`installer/assets-manifest.json` records upstream versions, URLs and hashes. `installer/payload-files.json` records packaged files and hashes. The resulting installer is unsigned unless a maintainer adds a separate signing step; a valid Microsoft prerequisite signature does not sign Franky's installer.

After the installer build, run `.\.venv\Scripts\python.exe scripts/package-sources.py` to make the separate **Bundled-Sources.zip** release companion. It verifies required source archive hashes and includes notices, upstream versions, and firmware relink materials. Run `scripts/package.py` for the smaller Windows source ZIP. Publish matching checksums for all downloads.

## Check a release

Run the checks in [CONTRIBUTING.md](../CONTRIBUTING.md), inspect the payload and source companion, and verify the final downloads' checksums. Test install, update, uninstall, saved settings, offline speech loading, provider setup, and optional USB flashing separately. Use a disposable Windows test machine for installation checks. A mocked flash test does not prove a physical robot upload worked.

The initial v0.5 preview passed automated tests, packaged speech/start/stop checks, a seven-page GUI check, and a small installer lifecycle fixture. A complete fresh-Windows install with prerequisite elevation remains unverified. Keep that limitation visible in release notes until a full test is completed.
