"""Console-only provider setup. Never enter API keys in chat or on the robot."""
import getpass
import sys
import requests
from settings import load_settings, save_settings, validate_url
from provider_config import PROVIDERS
from credential_store import get_key, save_key
from providers import list_models, ProviderError

def available_models(url):
    return list_models({"provider": "lmstudio", "base_url": url})

def prepare_key(provider):
    if provider == "lmstudio":
        return
    if get_key(provider):
        print("A key is already configured for this provider.")
        if input("Use it? [Y/n]: ").strip().lower() != "n":
            return
    if not sys.stdin.isatty():
        raise ValueError("Enter keys only in the interactive local setup window")
    print("Paste the key into this local window, never into a chat or GitHub issue.")
    key = getpass.getpass("Provider API key (hidden; blank cancels): ").strip()
    if not key:
        raise ValueError("No key entered; existing provider settings were not changed")
    if input("Save encrypted for this Windows user in bridge/.secrets? [y/N]: ").strip().lower() != "y":
        raise ValueError("Key was not saved; existing provider settings were not changed")
    save_key(provider, key)
    print("Protected key saved. It will not be included in a release package.")

def main():
    print("DigitalRCS Local LLM Chatbot - provider setup")
    print("LM Studio is the default. Providers never switch automatically.")
    old = load_settings()
    names = list(PROVIDERS)
    for number, provider in enumerate(names, 1):
        print(f"  {number}. {PROVIDERS[provider]['name']}")
    while True:
        try:
            selection = input("Provider number [1 = LM Studio]: ").strip() or "1"
            choice = int(selection)
            if not 1 <= choice <= len(names):
                raise ValueError("Choose a provider number from the list")
            provider = names[choice - 1]
            if provider == "lmstudio":
                print("Start LM Studio's API server and load a chat model first.")
                print("Same PC: http://127.0.0.1:1234/v1. Another PC: use that PC's address.")
                url = validate_url(input(f"LM Studio address [{old['lm_studio_url']}]: ").strip() or old['lm_studio_url'])
            else:
                print("Online mode sends transcribed conversation text to this provider. Speech stays local.")
                print("OpenAI is metered. OpenRouter is restricted to free model IDs. Gemini can charge on paid accounts/models.")
                if input("Continue with this online provider? [y/N]: ").strip().lower() != "y":
                    return
                prepare_key(provider)
                url = PROVIDERS[provider]["url"]
            models = list_models({"provider": provider, "base_url": url})
            if not models:
                raise ValueError("No models found. Check account access or load a model in LM Studio.")
            for number, name in enumerate(models, 1):
                print(f"  {number}. {name}")
            print("Choose a text chat model. A listed ID does not guarantee chat support or free-tier eligibility.")
            value = input("Model number or exact model ID: ").strip()
            if value.isdigit():
                index = int(value)
                if not 1 <= index <= len(models):
                    raise ValueError("Choose a model number from the list")
                model = models[index - 1]
            else:
                if value not in models:
                    raise ValueError("Use an exact model ID from the list")
                model = value
            save_settings(url, model, provider=provider)
            print("Provider saved. Restart START-FRANKY to use the new settings.")
            return
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
            # Never print remote response bodies or exception request headers.
            if isinstance(exc, ProviderError):
                print(str(exc))
            else:
                print("Setup could not finish. Check the selected number, address, credentials, and model access.")
            if input("Try again? [Y/n]: ").strip().lower() == "n":
                raise SystemExit(1)

if __name__ == "__main__":
    main()
