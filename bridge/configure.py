"""Interactive connection wizard. Never writes API tokens."""
import os
import requests
from settings import load_settings, save_settings, validate_url

def available_models(url):
    headers = {}
    if os.environ.get("LM_STUDIO_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["LM_STUDIO_TOKEN"]
    response = requests.get(url + "/models", headers=headers, timeout=(5, 20))
    response.raise_for_status()
    data = response.json()
    return [item["id"] for item in data["data"] if isinstance(item.get("id"), str)]

def main():
    print("DigitalRCS Local LLM Chatbot - connection setup")
    print("Start LM Studio's API server and load a chat model first.")
    print("Same PC: http://127.0.0.1:1234/v1")
    print("Another PC: use that PC's network address, port, and /v1.")
    old = load_settings()
    while True:
        try:
            url = validate_url(input(f"LM Studio address [{old['lm_studio_url']}]: ").strip() or old['lm_studio_url'])
            models = available_models(url)
            if not models:
                raise ValueError("No models found. Load a chat model in LM Studio first.")
            for number, name in enumerate(models, 1):
                print(f"  {number}. {name}")
            choice = int(input("Choose the number of your CHAT model (not an embedding model): "))
            if not 1 <= choice <= len(models):
                raise ValueError("Choose a number from the list")
            save_settings(url, models[choice - 1])
            print("Connection settings saved. You can rerun setup to change them.")
            return
        except (requests.RequestException, ValueError, KeyError, TypeError):
            print("Could not finish setup. Check the address, server, loaded model, and number selected.")
            if input("Try again? [Y/n]: ").lower() == "n":
                raise SystemExit(1)

if __name__ == "__main__":
    main()
