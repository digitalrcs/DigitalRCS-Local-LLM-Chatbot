"""Wizard-owned bridge process with a local, per-run shutdown request."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))


def main(token):
    import uvicorn
    state = ROOT / "logs"
    state.mkdir(exist_ok=True)
    instance = state / "bridge-instance.json"
    stop = state / "bridge-stop.json"
    server = uvicorn.Server(uvicorn.Config("server:app", host="0.0.0.0", port=8766, log_level="info"))
    finished = threading.Event()
    instance_id = uuid.uuid4().hex
    os.environ["FRANKY_INSTANCE_ID"] = instance_id

    def watch():
        # Publish ownership only after this particular process has bound its port.
        while not finished.wait(0.25):
            if server.started:
                temporary = state / ("bridge-instance-" + token + ".tmp")
                temporary.write_text(json.dumps({"token": token, "instance_id": instance_id, "pid": os.getpid()}))
                temporary.replace(instance)
                break
        while not finished.wait(0.25):
            try:
                if json.loads(stop.read_text()).get("token") == token:
                    server.should_exit = True
                    return
            except (OSError, ValueError, AttributeError):
                pass
    threading.Thread(target=watch, daemon=True).start()
    try:
        server.run()
    finally:
        finished.set()
        for path in (instance, stop):
            try:
                if json.loads(path.read_text()).get("token") == token:
                    path.unlink()
            except (OSError, ValueError, AttributeError):
                pass


if __name__ == "__main__":
    value = sys.argv[1] if len(sys.argv) == 2 else ""
    if len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        raise SystemExit("Start the bridge from Franky Setup.")
    main(value)
