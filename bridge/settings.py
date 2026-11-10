"""Portable configuration; environment variables override local settings."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
CONFIG = Path(__file__).resolve().parent / "config.json"

def validate_url(value):
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/v1"):
        raise ValueError("Use http://COMPUTER-ADDRESS:1234/v1 without a password or query in the address")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Invalid server port") from exc
    return value

def load_settings(path=CONFIG):
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config.json must contain a settings object")
    url = validate_url(os.environ.get("LM_STUDIO_URL", data.get("lm_studio_url", "http://127.0.0.1:1234/v1")))
    model = os.environ.get("LM_STUDIO_MODEL", data.get("lm_studio_model", ""))
    if not isinstance(model, str):
        raise ValueError("Model name must be text")
    return {"lm_studio_url": url, "lm_studio_model": model.strip()}

def save_settings(url, model, path=CONFIG):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Choose a loaded chat model")
    data = {"lm_studio_url": validate_url(url), "lm_studio_model": model.strip()}
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
