"""Windows-user-protected credentials; never exposed through HTTP or config.json."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
from provider_config import PROVIDERS

ROOT = Path(__file__).resolve().parent / ".secrets"

class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(raw, encrypt):
    if os.name != "nt":
        raise ValueError("Use the provider environment variable on non-Windows systems")
    storage = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, output = Blob(len(raw), storage), Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if encrypt:
        fn = crypt32.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), "DigitalRCS provider key", None, None, None, 1, ctypes.byref(output))
    else:
        fn = crypt32.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    if not ok:
        raise ValueError("Could not access the protected provider key; enter it again on this PC")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(output.data)

def get_key(provider):
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    value = os.environ.get(PROVIDERS[provider]["key_env"], "").strip()
    if value:
        return value
    path = ROOT / (provider + ".dpapi")
    return _crypt(path.read_bytes(), False).decode("utf-8") if path.exists() else ""

def save_key(provider, value):
    if provider not in PROVIDERS or not value or any(c.isspace() for c in value):
        raise ValueError("Invalid provider key")
    protected = _crypt(value.encode("utf-8"), True)
    ROOT.mkdir(exist_ok=True)
    path = ROOT / (provider + ".dpapi")
    temp = path.with_suffix(".tmp")
    temp.write_bytes(protected)
    temp.replace(path)
