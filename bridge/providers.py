"""Explicit routing; no automatic provider switching or paid fallback."""
import requests
from provider_config import PROVIDERS, validate_model
from credential_store import get_key

class ProviderError(ValueError):
    pass

def headers_for(provider):
    key = get_key(provider)
    if provider != "lmstudio" and not key:
        raise ProviderError("Provider key not configured. Run CHANGE-PROVIDER locally on the PC.")
    return {"Authorization": "Bearer " + key} if key else {}

def endpoint(config):
    return config["base_url"] if config["provider"] == "lmstudio" else PROVIDERS[config["provider"]]["url"]

def check_response(response):
    messages = {401: "Provider rejected the key; update it locally.", 403: "This key or account cannot access the selected model.",
                402: "Provider credit or billing limit reached. No fallback was attempted.",
                429: "Provider rate limit reached. Try later; no paid fallback was attempted."}
    if response.status_code in messages:
        raise ProviderError(messages[response.status_code])
    if not 200 <= response.status_code < 300:
        raise ProviderError("Provider request failed. Check the selected model and service status.")

def list_models(config):
    response = requests.get(endpoint(config) + "/models", headers=headers_for(config["provider"]), timeout=(5, 20), allow_redirects=False)
    check_response(response)
    ids = [item["id"] for item in response.json()["data"] if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if config["provider"] == "openrouter":
        ids = [x for x in ids if x.endswith(":free")]
        ids.insert(0, "openrouter/free")
    return list(dict.fromkeys(ids))

def generate_reply(config, messages):
    provider, model = config["provider"], config["model"]
    if not model:
        raise ProviderError("Choose a chat model with START-HERE or CHANGE-PROVIDER.")
    validate_model(provider, model)
    if provider == "openai":
        path = "/responses"
        payload = {"model": model, "input": messages, "max_output_tokens": config["max_output_tokens"], "store": False}
    else:
        path = "/chat/completions"
        payload = {"model": model, "messages": messages, "stream": False, "max_tokens": config["max_output_tokens"]}
    try:
        response = requests.post(endpoint(config) + path, json=payload, headers=headers_for(provider), timeout=(5, 50), allow_redirects=False)
        check_response(response)
        data = response.json()
        if provider == "openai":
            if data.get("status") != "completed":
                raise ProviderError("OpenAI did not finish its reply. Choose a faster model or adjust the output limit.")
            parts = []
            for item in data.get("output", []):
                if item.get("type") == "message" and item.get("role") == "assistant":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text": parts.append(part["text"])
                        elif part.get("type") == "refusal": parts.append(part["refusal"])
            text = " ".join(parts)
        else:
            text = data["choices"][0]["message"]["content"]
        if not isinstance(text, str):
            raise ProviderError("Provider did not return a spoken-text reply.")
        if "</think>" in text:
            text = text.split("</think>")[-1]
        text = text.strip()
        if "<think>" in text or not text:
            raise ProviderError("Model did not return a final answer.")
        return text
    except requests.RequestException as exc:
        raise ProviderError("Provider unavailable or timed out. Check its connection and model.") from exc
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError("Provider returned an invalid reply.") from exc
