"""Optional LA064 USB flashing with a verified, prebuilt firmware bundle.

Importing this module and listing ports never opens a serial connection. A
confirmed flash probes the selected port, backs up settings, then writes only
the four firmware regions. The caller must not terminate the worker mid-write.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
from uuid import uuid4


_PORT = re.compile(r"COM[1-9][0-9]{0,4}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z", re.ASCII)
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_LIMITS = {0x0: 0x8000, 0x8000: 0x1000, 0xE000: 0x2000, 0x10000: 0x300000}
_BACKUP_OFFSET, _BACKUP_SIZE = 0x8000, 0x8000
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_PORT_LABELS = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Get-CimInstance Win32_PnPEntity -ErrorAction Stop |
  Where-Object { $_.Name -match '\(COM[1-9][0-9]*\)$' } |
  ForEach-Object {
    if ($_.Name -match '\((COM[1-9][0-9]*)\)$') {
      [pscustomobject]@{ port=$Matches[1]; description=$_.Name }
    }
  } | ConvertTo-Json -Compress
"""


def driver_help() -> str:
    """Official driver help; never downloads or installs a driver automatically."""
    return "https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers"


def _safe_line(value: object) -> str:
    text = _ANSI.sub("", str(value))
    return "".join(c for c in text if c >= " " and c != "\x7f")[:400].strip()


def _emit(emit, message: str, percent: int | None = None) -> None:
    event = {"type": "progress", "message": _safe_line(message)}
    if percent is not None:
        event["percent"] = max(0, min(100, percent))
    try:
        emit(event)
    except Exception:
        # Closing a GUI or a failed callback must not interrupt a flash write.
        pass


def _registry_ports() -> set[str]:
    try:
        import winreg
    except ImportError:
        return set()
    ports = set()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            index = 0
            while True:
                try:
                    _, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                if isinstance(value, str) and _PORT.fullmatch(value):
                    ports.add(value)
                index += 1
    except OSError:
        pass
    return ports


def _descriptions() -> dict[str, str]:
    if os.name != "nt":
        return {}
    try:
        environment = os.environ.copy()
        shell_home = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/WindowsPowerShell/v1.0"
        environment["PSModulePath"] = str(shell_home / "Modules")
        result = subprocess.run(
            [str(shell_home / "powershell.exe"), "-NoProfile", "-NonInteractive", "-Command", _PORT_LABELS],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, creationflags=_NO_WINDOW, check=False, env=environment,
        )
        if result.returncode or not result.stdout.strip():
            return {}
        rows = json.loads(result.stdout)
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return {}
        return {row["port"]: _safe_line(row.get("description", "USB serial device"))
                for row in rows if isinstance(row, dict)
                and isinstance(row.get("port"), str) and _PORT.fullmatch(row["port"])}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def list_ports() -> list[dict[str, str]]:
    """Enumerate current Windows serial ports without opening or resetting them."""
    ports = _registry_ports()
    labels = _descriptions() if ports else {}
    return [{"port": port, "description": labels.get(port, "Serial device")}
            for port in sorted(ports, key=lambda item: int(item[3:]))]


def _within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("An installer path points outside its installation folder.")
    return resolved


def _verify_image(image: dict) -> None:
    path = image["path"]
    if not path.is_file() or not 0 < path.stat().st_size <= _LIMITS[image["offset"]]:
        raise ValueError("A firmware image is missing or exceeds its allowed flash region.")
    if image["offset"] == 0xE000 and path.stat().st_size != 0x2000:
        raise ValueError("The boot selection image must be exactly 8 KB.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != image["sha256"]:
        raise ValueError("Firmware verification failed. Download a fresh installer.")


def _payload(root: Path) -> tuple[str, Path, list[dict]]:
    firmware = _within(root, root / "installer" / "firmware")
    manifest_path = _within(root, firmware / "manifest.json")
    if not manifest_path.is_file() or manifest_path.stat().st_size > 65536:
        raise ValueError("The prebuilt firmware manifest is missing or invalid.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("chip") != "esp32s3" or manifest.get("flash_size") != "16MB":
        raise ValueError("This firmware bundle must target the LA064 ESP32-S3 with 16 MB flash.")
    version = manifest.get("version")
    files = manifest.get("files")
    if not isinstance(version, str) or not version.strip() or len(version) > 80:
        raise ValueError("The firmware version is missing or invalid.")
    if not isinstance(files, list) or len(files) != 4:
        raise ValueError("The firmware bundle must contain four separate images.")
    images, offsets, names = [], set(), set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("Invalid firmware image entry.")
        name, offset, digest = entry.get("name"), entry.get("offset"), entry.get("sha256")
        if (not isinstance(name, str) or not name.lower().endswith(".bin")
                or any(c in name for c in '/\\:\x00') or "merged" in name.lower()
                or name.casefold() in names or Path(name).name != name):
            raise ValueError("Firmware must use separate, local image files.")
        if isinstance(offset, str):
            try:
                offset = int(offset, 0)
            except ValueError as exc:
                raise ValueError("Invalid firmware offset.") from exc
        if type(offset) is not int or offset not in _LIMITS or offset in offsets:
            raise ValueError("Firmware offsets do not match the supported LA064 layout.")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("A firmware checksum is missing or invalid.")
        image = {"path": _within(root, firmware / name), "offset": offset, "sha256": digest.lower()}
        _verify_image(image)
        images.append(image)
        offsets.add(offset)
        names.add(name.casefold())
    tool = _within(root, root / "installer" / "tools" / "esptool.exe")
    if not tool.is_file():
        raise ValueError("The standalone flashing tool is missing. Download a fresh installer.")
    return version, tool, sorted(images, key=lambda item: item["offset"])


def _run(args: list[str], emit, *, timeout: int, percent: int) -> tuple[int, str]:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, creationflags=_NO_WINDOW, check=False)
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    for line in output.splitlines():
        if _safe_line(line):
            _emit(emit, line, percent)
    return result.returncode, output


def _write(args: list[str], images: list[dict], emit) -> int:
    # No timeout/terminate: an interrupted write could leave an unbootable robot.
    regions = [(image["offset"], image["path"].stat().st_size) for image in images]
    total = sum(size for _, size in regions)
    last_percent = 25
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=_NO_WINDOW)
    try:
        for line in process.stdout:
            progress = re.search(r"(?:\(|\s)(\d{1,3})(?:\.\d+)?\s*%", line)
            address = re.search(r"Writing at\s+(0x[0-9a-fA-F]+)", line)
            percent = None
            if progress and address:
                at, completed = int(address[1], 16), 0
                for offset, size in regions:
                    if offset <= at <= offset + size:
                        done = completed + size * min(100, int(progress[1])) / 100
                        last_percent = max(last_percent, 25 + int(70 * done / total))
                        percent = last_percent
                        break
                    completed += size
            if _safe_line(line):
                _emit(emit, line, percent)
        return process.wait()
    finally:
        process.stdout.close()


def flash_robot(root: Path, port: str, confirmed: bool, emit) -> dict:
    """Flash only after explicit LA064 N16R8 confirmation and current COM choice.

    Returns {ok, stage, message, ...}; failures never continue to the next stage.
    A successful private backup is retained and returned even if writing fails.
    """
    stage, backup, version = "validation", None, None
    try:
        if confirmed is not True:
            raise ValueError("Confirm that the selected robot is a LAFVIN LA064 ESP32-S3 N16R8 before flashing.")
        if not isinstance(port, str) or not _PORT.fullmatch(port):
            raise ValueError("Select a valid COM port from the connected-device list.")
        if port not in {item["port"] for item in list_ports()}:
            raise ValueError("The selected COM port is no longer available. Reconnect the robot and refresh the list.")
        root = Path(root).resolve(strict=True)
        version, tool, images = _payload(root)
        _emit(emit, "Verified the four LA064 firmware images.", 5)
        base = [str(tool), "--chip", "esp32s3", "--port", port, "--baud", "115200",
                "--before", "default-reset", "--after", "hard-reset"]
        stage = "probe"
        _emit(emit, "Checking the selected robot's chip and flash capacity...", 10)
        code, output = _run([*base, "flash-id"], emit, timeout=60, percent=10)
        if code:
            raise ValueError("Could not identify the robot. Close serial monitors and check the USB data cable and selected port.")
        chip = re.search(r"^\s*Chip\s+(?:is\s+|type:\s*)(ESP32(?:-[A-Z0-9]+)?)(?=\s|\(|$)", output, re.MULTILINE | re.IGNORECASE)
        capacity = re.search(r"Detected flash size:\s*(\d+)\s*(KB|MB)\b", output, re.IGNORECASE)
        if not chip or chip[1].upper() != "ESP32-S3":
            raise ValueError("The selected device was not identified as an ESP32-S3. No firmware was written.")
        if not capacity or capacity[1] != "16" or capacity[2].upper() != "MB":
            raise ValueError("The selected device does not report 16 MB flash. No firmware was written.")
        stage = "backup"
        folder = _within(root, root / "private-backups")
        folder.mkdir(parents=False, exist_ok=True)
        folder = _within(root, folder)
        name = f"franky-settings-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{port}-{uuid4().hex[:8]}.bin"
        candidate = _within(root, folder / name)
        if candidate.exists():
            raise ValueError("The settings backup destination already exists. Retry to create a new backup.")
        _emit(emit, "Saving a private backup of the partition table and settings...", 20)
        code, _ = _run([*base, "read-flash", hex(_BACKUP_OFFSET), hex(_BACKUP_SIZE), str(candidate)],
                       emit, timeout=120, percent=20)
        if code or not candidate.is_file() or candidate.stat().st_size != _BACKUP_SIZE:
            raise ValueError("The settings backup could not be verified. No firmware was written.")
        backup = str(candidate)
        for image in images:
            _verify_image(image)  # Detect bundle changes during the probe/backup.
        stage = "write"
        _emit(emit, "Installing Franky. Keep the robot connected until verification finishes.", 25)
        args = [*base, "write-flash", "--flash-mode", "keep", "--flash-freq", "keep", "--flash-size", "keep"]
        for image in images:
            args.extend([hex(image["offset"]), str(image["path"])])
        if _write(args, images, emit):
            raise ValueError("Firmware upload failed. Keep the settings backup and retry with the same robot; do not erase its flash.")
        message = "Franky firmware uploaded and verified. The robot is restarting."
        _emit(emit, message, 100)
        return {"ok": True, "stage": "complete", "message": message, "version": version, "port": port, "backup": backup}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            message = "The robot did not respond in time. Check its connection and retry. No firmware write was started."
        elif isinstance(exc, OSError):
            message = "Could not access the installer files or USB flashing tool. Check permissions and retry."
        else:
            message = _safe_line(exc)
        _emit(emit, message)
        result = {"ok": False, "stage": stage, "message": message}
        if backup:
            result["backup"] = backup
        return result
