"""Explicit routing; no automatic provider switching or paid fallback."""
import json
import requests
from provider_config import PROVIDERS, validate_model
from credential_store import get_key

THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


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

def list_models(config, timeout=(5, 20)):
    response = requests.get(endpoint(config) + "/models", headers=headers_for(config["provider"]), timeout=timeout, allow_redirects=False)
    check_response(response)
    ids = [item["id"] for item in response.json()["data"] if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if config["provider"] == "openrouter":
        ids = [x for x in ids if x.endswith(":free")]
        ids.insert(0, "openrouter/free")
    return list(dict.fromkeys(ids))


def voice_messages(config, messages):
    """Return a copy of messages with model reasoning switched off where supported.

    Qwen3-family chat templates honour a trailing "/no_think" in the prompt.
    Other models ignore the setting, so it is applied only to Qwen3 names.
    The caller's list and dictionaries are never modified.
    """
    if not config.get("disable_thinking", True) or "qwen3" not in config["model"].lower():
        return list(messages)
    if messages and messages[0].get("role") == "system":
        first = dict(messages[0])
        first["content"] = first["content"] + " /no_think"
        return [first, *messages[1:]]
    return [{"role": "system", "content": "/no_think"}, *messages]


def build_request(config, messages, stream=False):
    """Return (path, payload) for the configured provider."""
    provider, model = config["provider"], config["model"]
    if not model:
        raise ProviderError("Choose a chat model with START-HERE or CHANGE-PROVIDER.")
    validate_model(provider, model)
    messages = voice_messages(config, messages)
    if provider == "openai":
        return "/responses", {"model": model, "input": messages, "max_output_tokens": config["max_output_tokens"], "store": False}
    return "/chat/completions", {"model": model, "messages": messages, "stream": stream, "max_tokens": config["max_output_tokens"]}


def final_answer(text):
    """Remove complete reasoning blocks and reject replies without an answer."""
    if not isinstance(text, str):
        raise ProviderError("Provider did not return a spoken-text reply.")
    if THINK_CLOSE in text:
        text = text.split(THINK_CLOSE)[-1]
    text = text.strip()
    if THINK_OPEN in text or not text:
        raise ProviderError("Model did not return a final answer.")
    return text


def generate_reply(config, messages):
    path, payload = build_request(config, messages)
    try:
        response = requests.post(endpoint(config) + path, json=payload, headers=headers_for(config["provider"]), timeout=(5, 50), allow_redirects=False)
        check_response(response)
        data = response.json()
        if config["provider"] == "openai":
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
            choice = data["choices"][0]
            check_finish_reason(choice.get("finish_reason"))
            text = choice["message"]["content"]
        return final_answer(text)
    except requests.RequestException as exc:
        raise ProviderError("Provider unavailable or timed out. Check its connection and model.") from exc
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError("Provider returned an invalid reply.") from exc


class ReasoningFilter:
    """Drop <think>...</think> blocks from text that arrives in pieces.

    Text that might be the start of a tag is held back until the next piece
    shows whether it is a tag. feed() returns text that is safe to speak.
    """

    def __init__(self):
        self.pending = ""
        self.inside = False

    def feed(self, text):
        self.pending += text
        spoken = []
        while True:
            if self.inside:
                end = self.pending.find(THINK_CLOSE)
                if end < 0:
                    # Keep only a possible partial closing tag.
                    self.pending = self.pending[-(len(THINK_CLOSE) - 1):]
                    break
                self.pending = self.pending[end + len(THINK_CLOSE):]
                self.inside = False
                continue
            start = self.pending.find(THINK_OPEN)
            stray = self.pending.find(THINK_CLOSE)
            if stray >= 0 and (start < 0 or stray < start):
                # A closing tag without an opening tag: drop only the tag.
                spoken.append(self.pending[:stray])
                self.pending = self.pending[stray + len(THINK_CLOSE):]
                continue
            if start >= 0:
                spoken.append(self.pending[:start])
                self.pending = self.pending[start + len(THINK_OPEN):]
                self.inside = True
                continue
            safe = len(self.pending) - self._partial_tag_length()
            spoken.append(self.pending[:safe])
            self.pending = self.pending[safe:]
            break
        return "".join(spoken)

    def finish(self):
        """Return held-back text at the end of the stream."""
        text = "" if self.inside else self.pending
        self.pending = ""
        return text

    def _partial_tag_length(self):
        """Length of the longest suffix that could begin a tag."""
        for size in range(min(len(THINK_CLOSE) - 1, len(self.pending)), 0, -1):
            tail = self.pending[-size:]
            if THINK_OPEN.startswith(tail) or THINK_CLOSE.startswith(tail):
                return size
        return 0


def stream_reply(config, messages, stop=None):
    """Yield reply text in pieces as the model writes it, without reasoning.

    OpenAI's Responses API is not streamed here; its full reply is yielded at
    once so callers can treat every provider the same way.
    """
    if stop is not None and stop.is_set():
        return
    if config["provider"] == "openai":
        text = generate_reply(config, messages)
        if stop is None or not stop.is_set():
            yield text
        return
    path, payload = build_request(config, messages, stream=True)
    reasoning = ReasoningFilter()
    produced = False
    completed = False
    try:
        with requests.post(endpoint(config) + path, json=payload, headers=headers_for(config["provider"]),
                           timeout=(5, 50), allow_redirects=False, stream=True) as response:
            check_response(response)
            # SSE is UTF-8 even when the server omits charset. Requests would
            # otherwise choose ISO-8859-1 for text/event-stream.
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                # Poll even on reasoning-only/keep-alive events, not only when
                # the model finally produces spoken text.
                if stop is not None and stop.is_set():
                    return
                piece, completed = stream_event(line)
                text = reasoning.feed(piece or "")
                if text:
                    produced = produced or bool(text.strip())
                    yield text
                if completed:
                    break
        if stop is not None and stop.is_set():
            return
        if not completed:
            raise ProviderError("Provider stream ended before the reply completed. Please try again.")
        if reasoning.inside:
            raise ProviderError("Model did not return a final answer.")
        tail = reasoning.finish()
        if tail:
            produced = produced or bool(tail.strip())
            yield tail
    except requests.RequestException as exc:
        raise ProviderError("Provider unavailable or timed out. Check its connection and model.") from exc
    if not produced:
        raise ProviderError("Model did not return a final answer.")


def stream_delta(line):
    """Return the text in one server-sent event line, "" for none, None at the end."""
    return stream_event(line)[0]


def check_finish_reason(reason):
    if reason == "length":
        raise ProviderError("Model reached its output limit before finishing. Increase max_output_tokens in bridge/config.json.")
    if reason not in (None, "stop"):
        raise ProviderError("Provider did not complete a spoken-text reply.")


def stream_event(line):
    """Return (text, completed), rejecting malformed or truncated replies."""
    if not line or not line.startswith("data:"):
        return "", False
    data = line[5:].strip()
    if data == "[DONE]":
        return None, True
    try:
        event = json.loads(data)
        choices = event["choices"]
        # Optional usage-only SSE events do not contain a text choice.
        if choices == [] and isinstance(event.get("usage"), dict):
            return "", False
        choice = choices[0]
        if not isinstance(choice, dict):
            raise TypeError("Invalid choice")
        reason = choice.get("finish_reason")
        check_finish_reason(reason)
        delta = choice.get("delta") or {}
        if not isinstance(delta, dict):
            raise TypeError("Invalid delta")
    except ProviderError:
        raise
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Provider returned an invalid reply.") from exc
    # Separate reasoning fields (for example reasoning_content) are ignored.
    content = delta.get("content")
    return (content if isinstance(content, str) else ""), reason == "stop"
