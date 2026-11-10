"""Download the Kokoro v1.0 model and voice pack from the ONNX maintainer."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent / "models" / "kokoro"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"

def download(name):
    ROOT.mkdir(parents=True, exist_ok=True)
    dest = ROOT / name
    if dest.is_file():
        return
    partial = dest.with_suffix(dest.suffix + ".part")
    with requests.get(BASE + name, stream=True, timeout=(15, 60)) as response:
        response.raise_for_status()
        with partial.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                output.write(chunk)
    partial.replace(dest)
    print(f"Downloaded {name}: {dest.stat().st_size} bytes", flush=True)

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, ("kokoro-v1.0.onnx", "voices-v1.0.bin")))
