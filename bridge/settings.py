"""Portable configuration; environment variables override local settings."""
import json
import ipaddress
import os
from pathlib import Path
import re
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

def validate_public_bridge_url(value):
    """Validate an advertised LAN origin; it never changes the bind address."""
    if not isinstance(value, str):
        raise ValueError("Bridge address must be text")
    value = value.strip()
    if not value:
        return ""
    if len(value) > 150 or any(char.isspace() or ord(char) < 32 for char in value) or "?" in value or "#" in value:
        raise ValueError("Use an HTTP bridge address without spaces, a query or fragment")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid bridge host or port") from exc
    if (parsed.scheme != "http" or not host or port != 8766
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Use http://SERVER-ADDRESS:8766 without a password or path")
    host = host.rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Use the server's LAN address, not localhost")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Browsers interpret legacy numeric spellings (127.1, integers, hex)
        # differently. Require canonical IP literals or ordinary DNS labels.
        labels = host.split(".")
        if (not host or len(host) > 253 or re.fullmatch(r"[0-9.]+", host)
                or all(re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)", label) for label in labels)
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
            raise ValueError("Use a valid LAN IP address or DNS hostname")
        canonical = host
    else:
        mapped = getattr(address, "ipv4_mapped", None)
        if (address.is_loopback or address.is_unspecified or "%" in host
                or (mapped and (mapped.is_loopback or mapped.is_unspecified))):
            raise ValueError("Use the server's LAN address, not a loopback or unspecified address")
        if address.version != 4:
            raise ValueError("Franky needs an IPv4 address or DNS hostname")
        canonical = str(address)
    return f"http://{canonical}:8766"


def _read_config(path):
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config.json must contain a settings object")
    return data


def _write_config(data, path):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_settings(path=CONFIG):
    data = _read_config(path)
    url = validate_url(os.environ.get("LM_STUDIO_URL", data.get("lm_studio_url", "http://127.0.0.1:1234/v1")))
    model = os.environ.get("LM_STUDIO_MODEL", data.get("lm_studio_model", ""))
    if not isinstance(model, str):
        raise ValueError("Model name must be text")
    public_url = validate_public_bridge_url(os.environ.get("BRIDGE_PUBLIC_URL", data.get("public_bridge_url", "")))
    return resolve_provider(data, {"lm_studio_url": url, "lm_studio_model": model.strip(), "public_bridge_url": public_url})

def save_settings(url, model, path=CONFIG, provider="lmstudio"):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Choose a loaded chat model")
    validate_model(provider, model)
    old = load_settings(path)
    data = {"provider": provider, "model": model.strip(), "max_output_tokens": old["max_output_tokens"],
            "lm_studio_url": old["lm_studio_url"], "lm_studio_model": old["lm_studio_model"],
            "public_bridge_url": validate_public_bridge_url(_read_config(path).get("public_bridge_url", ""))}
    if provider == "lmstudio":
        data.update(lm_studio_url=validate_url(url), lm_studio_model=model.strip())
    _write_config(data, path)


def save_public_bridge_url(value, path=CONFIG):
    value = validate_public_bridge_url(value)
    data = _read_config(path)
    data["public_bridge_url"] = value
    _write_config(data, path)
    return value
