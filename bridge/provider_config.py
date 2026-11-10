"""Optional providers. Existing LM Studio settings remain the default."""
import os

PROVIDERS = {
    "lmstudio": {"name": "LM Studio (local, default)", "url": "http://127.0.0.1:1234/v1", "key_env": "LM_STUDIO_TOKEN"},
    "openai": {"name": "OpenAI API (online, metered)", "url": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY"},
    "openrouter": {"name": "OpenRouter free models (online, limited)", "url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY"},
    "gemini": {"name": "Google Gemini (check account/model free-tier eligibility)", "url": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY"},
}

def resolve_provider(data, local):
    provider = os.environ.get("CHAT_PROVIDER", data.get("provider", "lmstudio"))
    if provider not in PROVIDERS:
        raise ValueError("Choose lmstudio, openai, openrouter, or gemini")
    fallback = local["lm_studio_model"] if provider == "lmstudio" else data.get("model", "openrouter/free" if provider == "openrouter" else "")
    model = os.environ.get("CHAT_MODEL", fallback)
    if not isinstance(model, str):
        raise ValueError("Model must be text")
    limit = data.get("max_output_tokens", 1200)
    if type(limit) is not int or not 128 <= limit <= 4096:
        raise ValueError("max_output_tokens must be a whole number from 128 to 4096")
    validate_model(provider, model)
    return {"provider": provider, "base_url": local["lm_studio_url"] if provider == "lmstudio" else PROVIDERS[provider]["url"],
            "model": model.strip(), "max_output_tokens": limit, **local}

def validate_model(provider, model):
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    if provider == "openrouter" and model and not (model == "openrouter/free" or model.endswith(":free")):
        raise ValueError("OpenRouter accepts only openrouter/free or an explicit :free model")
