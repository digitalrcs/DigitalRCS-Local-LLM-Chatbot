"""Private stdin/stdout helper for the Windows wizard. Never serve setup over HTTP."""
import contextlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "installer"))
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ROUTING_OVERRIDES = ("CHAT_PROVIDER", "CHAT_MODEL", "LM_STUDIO_URL", "LM_STUDIO_MODEL", "BRIDGE_PUBLIC_URL")


@contextlib.contextmanager
def saved_routing():
    """The GUI's explicit saved choice wins over inherited shell routing."""
    previous = {name: os.environ.pop(name) for name in ROUTING_OVERRIDES if name in os.environ}
    try:
        yield
    finally:
        os.environ.update(previous)


def process_alive(pid):
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of exit.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class SetupError(ValueError):
    """An intentionally safe, actionable message for the setup window."""


def emit(event):
    print(json.dumps(event, ensure_ascii=True), flush=True)


def progress(message, percent=None):
    event = {"type": "progress", "message": message}
    if percent is not None:
        event["percent"] = percent
    emit(event)


def powershell(script, timeout=30):
    env = os.environ.copy()
    shell_home = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/WindowsPowerShell/v1.0"
    env["PSModulePath"] = str(shell_home / "Modules")
    script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); " + script
    return subprocess.run([str(shell_home / "powershell.exe"), "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                          timeout=timeout, creationflags=HIDDEN)


def lan_addresses():
    """List real connected adapters; keep the user's choice explicit."""
    if os.name == "nt":
        result = powershell("Get-NetIPConfiguration | Where-Object {$_.NetAdapter.Status -eq 'Up'} | ForEach-Object { $a=$_; $_.IPv4Address | ForEach-Object { [pscustomobject]@{ip=$_.IPAddress;label=$a.InterfaceAlias} } } | ConvertTo-Json -Compress")
        if result.returncode == 0 and result.stdout.strip():
            rows = json.loads(result.stdout)
            rows = [rows] if isinstance(rows, dict) else rows
        else:
            rows = []
    else:
        rows = [{"ip": item[4][0], "label": "Network"} for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    addresses, seen = [], set()
    for row in rows:
        try:
            address = ipaddress.ip_address(row["ip"])
        except (KeyError, ValueError):
            continue
        if address.version != 4 or address.is_loopback or address.is_link_local or address.is_unspecified or str(address) in seen:
            continue
        seen.add(str(address))
        addresses.append({"label": str(row.get("label", "Network")) + " - " + str(address), "url": f"http://{address}:8766"})
    return addresses


def lmstudio_paths():
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
    apps = [local / "Programs/LM Studio/LM Studio.exe", local / "LM-Studio/LM Studio.exe"]
    cli = [home / ".lmstudio/bin/lms.exe", home / ".cache/lm-studio/bin/lms.exe"]
    found = shutil.which("lms")
    if found:
        cli.insert(0, Path(found))
    return next((p for p in apps if p.is_file()), None), next((p for p in cli if p.is_file()), None)


class Worker:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.config = self.root / "bridge/config.json"
        self.state = self.root / "logs"

    def settings(self):
        from settings import load_settings
        with saved_routing():
            return load_settings(self.config)

    def instance(self):
        try:
            data = json.loads((self.state / "bridge-instance.json").read_text())
            if (isinstance(data, dict) and type(data.get("pid")) is int and data["pid"] > 0
                    and all(isinstance(data.get(name), str) and len(data[name]) == 32
                            and all(c in "0123456789abcdef" for c in data[name]) for name in ("token", "instance_id"))):
                return data
        except (OSError, ValueError):
            pass
        return None

    def owned_health(self, health):
        state = self.instance()
        return bool(health and state and health.get("instance_id") == state["instance_id"])

    def health(self):
        import requests
        try:
            response = requests.get("http://127.0.0.1:8766/health", timeout=(1, 2), allow_redirects=False)
            data = response.json()
            if response.status_code == 200 and data.get("status") == "ok" and "tts_engine" in data:
                return data
        except (requests.RequestException, ValueError, AttributeError):
            pass
        return None

    def models_ready(self):
        files = ["kokoro/kokoro-v1.0.onnx", "kokoro/voices-v1.0.bin", "whisper-base.en/model.bin", "whisper-tiny.en/model.bin"]
        return all((self.root / "bridge/models" / name).is_file() for name in files)

    def inspect(self, request):
        from credential_store import get_key
        from flash_robot import list_ports
        config = self.settings()
        try:
            configured = bool(get_key(config["provider"]))
        except ValueError:
            configured = False
        app, cli = lmstudio_paths()
        return {"provider": config["provider"], "base_url": config["base_url"], "model": config["model"],
                "public_bridge_url": config["public_bridge_url"], "key_configured": configured,
                "models_ready": self.models_ready(), "bridge_running": bool(self.health()),
                "lan_addresses": lan_addresses(), "ports": list_ports(), "lmstudio_installed": bool(app or cli)}

    @contextlib.contextmanager
    def provider(self, request):
        from provider_config import PROVIDERS
        from settings import validate_url
        provider = request.get("provider", "lmstudio")
        if provider not in PROVIDERS:
            raise SetupError("Choose an answer service from the list.")
        if provider != "lmstudio" and request.get("online_consent") is not True:
            raise SetupError("Please confirm that this online service receives conversation text and may charge your account.")
        url = validate_url(request.get("base_url", "http://127.0.0.1:1234/v1")) if provider == "lmstudio" else PROVIDERS[provider]["url"]
        key = request.get("key", "")
        if not isinstance(key, str) or any(c.isspace() for c in key):
            raise SetupError("Paste a key without spaces, or leave it blank to keep the saved key.")
        env_name = PROVIDERS[provider]["key_env"]
        previous = os.environ.get(env_name)
        try:
            if key:
                os.environ[env_name] = key
            yield {"provider": provider, "base_url": url}
        finally:
            if previous is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = previous

    def models(self, request):
        import requests
        from providers import list_models
        with self.provider(request) as config:
            progress("Checking which chat models are available...")
            try:
                ids = list_models(config)
            except requests.RequestException:
                if config["provider"] == "lmstudio":
                    raise SetupError("Cannot reach LM Studio. Open it, download a chat model, and start its server. For another PC, check its network address and server settings, then try again.") from None
                raise SetupError("Cannot reach the online provider. Check the Internet connection and try again.") from None
        if not ids:
            raise SetupError("No models found yet. In LM Studio, download a chat model and start its server, then click Find models again.")
        return {"models": ids}

    def save_provider(self, request):
        from settings import save_settings
        from credential_store import save_key, ROOT as secrets_root
        from provider_config import PROVIDERS
        if self.health():
            raise SetupError("Stop the bridge on the Try it page before changing its answer service.")
        model = request.get("model", "")
        ids = self.models(request)["models"]
        if not isinstance(model, str) or model not in ids:
            raise SetupError("Choose a model from Find models before saving.")
        provider = request.get("provider", "lmstudio")
        env = PROVIDERS[provider]["key_env"]
        if request.get("key") and os.environ.get(env):
            raise SetupError(f"This Windows session already sets {env}. Remove that override before saving a different key.")
        old_config = self.config.read_bytes() if self.config.is_file() else None
        key_path = secrets_root / (provider + ".dpapi")
        old_key = key_path.read_bytes() if key_path.is_file() else None
        try:
            if request.get("key"):
                save_key(provider, request["key"])
            with saved_routing():
                save_settings(request.get("base_url", "http://127.0.0.1:1234/v1"), model, self.config, provider)
        except Exception:
            if old_config is not None:
                self.config.write_bytes(old_config)
            elif self.config.exists():
                self.config.unlink()
            if old_key is not None:
                key_path.write_bytes(old_key)
            elif key_path.exists():
                key_path.unlink()
            raise
        return {"provider": provider, "model": model}

    def prepare_voice(self, request):
        from neural_voice import prepare
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model
        from download_voice import download
        progress("Checking Franky's voice files...", 10)
        for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            download(name)
        prepare()
        for index, name in enumerate(("base.en", "tiny.en")):
            folder = self.root / "bridge/models" / ("whisper-" + name)
            if not (folder / "model.bin").is_file():
                progress("Getting the English listening model. Completed downloads are kept...", 35 + index * 25)
                download_model(name, output_dir=str(folder))
            progress("Checking the English listening model...", 50 + index * 25)
            model = WhisperModel(str(folder), device="cpu", compute_type="int8", local_files_only=True)
            del model
        progress("Voice and listening files are ready. Try the voice preview next.", 100)
        return {"ready": True}

    def preview(self, request):
        from neural_voice import synthesize
        self.state.mkdir(exist_ok=True)
        target = self.state / "setup-preview.wav"
        pcm = synthesize("Hello! I'm Franky. My voice is ready. Let's have a chat.")
        with wave.open(str(target), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(pcm)
        return {"path": str(target)}

    def save_address(self, request):
        from settings import save_public_bridge_url
        if self.health():
            raise SetupError("Stop the bridge on the Try it page before changing its address.")
        return {"url": save_public_bridge_url(request.get("url", ""), self.config)}

    def allow_firewall(self, request):
        # Only the fixed, reviewed script runs elevated; provider setup stays as this user.
        script = self.root / "scripts/allow-lan.ps1"
        quoted = str(script).replace("'", "''")
        result = powershell("$p=Start-Process (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','\"" + quoted + "\"'); exit $p.ExitCode", timeout=180)
        if result.returncode:
            raise SetupError("Windows did not approve home-network access. Ask the PC's administrator, or try again. The bridge still works on this PC.")
        return {"enabled": True}

    def install_lmstudio(self, request):
        winget = shutil.which("winget")
        if not winget:
            raise SetupError("Use the Download LM Studio link, install it, and open it once. Then return here.")
        progress("Installing LM Studio. This can take several minutes...")
        result = subprocess.run([winget, "install", "--id", "ElementLabs.LMStudio", "--exact", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"], capture_output=True, timeout=1200, creationflags=HIDDEN)
        if result.returncode:
            app, cli = lmstudio_paths()
            if not app and not cli:
                raise SetupError("LM Studio could not install automatically. Use Download LM Studio, then open it and return here.")
        return {"installed": True}

    def start_lmstudio(self, request):
        app, cli = lmstudio_paths()
        if app:
            # This is the interactive model chooser requested by the user.
            os.startfile(str(app))
        if not cli:
            raise SetupError("Open LM Studio once, choose its recommended chat model, and let the download finish. Then click Start LM Studio again.")
        progress("Starting LM Studio's local connection...")
        result = subprocess.run([str(cli), "server", "start", "--port", "1234", "--bind", "127.0.0.1"], capture_output=True, timeout=90, creationflags=HIDDEN)
        if result.returncode:
            raise SetupError("In LM Studio, open Developer and start the server. Then return here and click Find models.")
        return {"started": True}

    def start_bridge(self, request):
        existing = self.health()
        if existing:
            if self.owned_health(existing):
                return {"url": "http://localhost:8766", "already_running": True}
            raise SetupError("Another Franky installation is running on this PC. Stop its original window or setup panel, then start this copy.")
        previous = self.instance()
        if previous and process_alive(previous["pid"]):
            raise SetupError("Franky is still starting or stopping. Wait a moment before trying again.")
        if not self.settings()["model"]:
            raise SetupError("Choose and save an answer service first.")
        self.state.mkdir(exist_ok=True)
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", 8766))
            except OSError:
                raise SetupError("Another program is using port 8766. Close it before starting Franky.") from None
        token = uuid.uuid4().hex
        environment = os.environ.copy()
        for name in ROUTING_OVERRIDES:
            environment.pop(name, None)
        with (self.state / "bridge.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, "-I", "-X", "utf8", str(self.root / "installer/bridge_runner.py"), token], cwd=self.root,
                                       stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=HIDDEN, env=environment)
        for _ in range(80):
            if self.owned_health(self.health()):
                return {"url": "http://localhost:8766"}
            if process.poll() is not None:
                break
            time.sleep(0.25)
        raise SetupError("The bridge did not start. Use Check readiness, or inspect logs/bridge.log in the installation folder.")

    def stop_bridge(self, request):
        state_path = self.state / "bridge-instance.json"
        if not state_path.is_file():
            if self.health():
                raise SetupError("This bridge was started outside the wizard. Stop its original window with Ctrl+C.")
            return {"stopped": True}
        state = self.instance()
        if state is None:
            raise SetupError("Bridge ownership could not be verified. Stop its original window instead.")
        health = self.health()
        if health and not self.owned_health(health):
            raise SetupError("Another Franky installation is running. Stop its original window or setup panel instead.")
        token = state["token"]
        temporary = self.state / ("bridge-stop-" + token + ".tmp")
        temporary.write_text(json.dumps({"token": token}))
        temporary.replace(self.state / "bridge-stop.json")
        for _ in range(80):
            current = self.instance()
            if (current is None or current["token"] != token) and not process_alive(state["pid"]):
                return {"stopped": True}
            if not process_alive(state["pid"]):
                if current and current["token"] == token:
                    state_path.unlink(missing_ok=True)
                return {"stopped": True}
            time.sleep(0.25)
        raise SetupError("Franky is finishing a request. Wait a moment, then check again.")

    def check_ready(self, request):
        import requests
        health = self.health()
        if not health:
            raise SetupError("Start the bridge first. If it just started, wait a few seconds and check again.")
        if not self.owned_health(health):
            raise SetupError("These services belong to another Franky installation. Stop that copy, then start this one from the wizard.")
        try:
            response = requests.get("http://127.0.0.1:8766/ready", timeout=(2, 5), allow_redirects=False)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data.get("checks"), dict):
                raise ValueError("Unexpected readiness")
            return data
        except (requests.RequestException, ValueError):
            raise SetupError("Start the bridge first. If it just started, wait a few seconds and check again.") from None

    def dispatch(self, request):
        if not isinstance(request, dict):
            raise SetupError("Setup received an invalid request.")
        action = request.get("action")
        if action == "lan_addresses":
            return {"addresses": lan_addresses()}
        if action == "list_ports":
            from flash_robot import list_ports
            return {"ports": list_ports()}
        if action == "flash":
            from flash_robot import flash_robot
            result = flash_robot(self.root, request.get("port", ""), request.get("confirmed") is True, emit)
            if result.get("ok") is False:
                raise SetupError(result.get("message", "The upload did not finish. Check the USB cable and try again."))
            return result
        allowed = {"inspect", "models", "save_provider", "prepare_voice", "preview", "save_address", "allow_firewall", "install_lmstudio", "start_lmstudio", "start_bridge", "stop_bridge", "check_ready"}
        if action not in allowed:
            raise SetupError("This setup action is not supported.")
        return getattr(self, action)(request)


def main():
    from providers import ProviderError
    try:
        raw = sys.stdin.readline(32769)
        if len(raw) > 32768:
            raise SetupError("The setup request is too long.")
        request = json.loads(raw)
        result = Worker().dispatch(request)
        emit({"type": "result", "ok": True, "data": result})
        return 0
    except (SetupError, ProviderError) as exc:
        emit({"type": "result", "ok": False, "error": str(exc), "data": {}})
    except Exception:
        # Never expose provider exceptions, request bodies, keys, or headers.
        emit({"type": "result", "ok": False, "error": "That step could not finish. Check the connection and try again. Your completed setup files are kept.", "data": {}})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
