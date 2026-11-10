"""Portable configuration; environment variables override local settings."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from provider_config import resolve_provider, validate_model
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
    return resolve_provider(data, {"lm_studio_url": url, "lm_studio_model": model.strip()})

def save_settings(url, model, path=CONFIG, provider="lmstudio"):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Choose a loaded chat model")
    validate_model(provider, model)
    old = load_settings(path)
    data = {"provider": provider, "model": model.strip(), "max_output_tokens": old["max_output_tokens"],
            "lm_studio_url": old["lm_studio_url"], "lm_studio_model": old["lm_studio_model"]}
    if provider == "lmstudio":
        data.update(lm_studio_url=validate_url(url), lm_studio_model=model.strip())
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
