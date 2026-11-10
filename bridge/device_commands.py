"""Recognize explicit device controls; never infer actions from an LLM reply."""
import re

SMALL = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))

def percentage(text):
    text = re.sub(r"\s+(?:percent|percentage points?)$", "", text.strip())
    if re.fullmatch(r"\d{1,3}", text):
        value = int(text)
    elif text in ("one hundred", "a hundred", "hundred"):
        value = 100
    elif text in SMALL:
        value = SMALL[text]
    else:
        parts = text.split()
        if not parts or parts[0] not in TENS or len(parts) > 2:
            return None
        value = TENS[parts[0]]
        if len(parts) == 2:
            if parts[1] not in SMALL or not 1 <= SMALL[parts[1]] <= 9:
                return None
            value += SMALL[parts[1]]
    return value if 0 <= value <= 100 else None

def parse_control(text):
    text = text.lower().replace("’", "'").replace("%", " percent")
    text = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text)
    text = re.sub(r"[,!?;]", " ", text)
    text = re.sub(r"\.(?=\s|$)", " ", text)
    text = " ".join(text.split())
    text = re.sub(r"^(?:(?:hey |hi )?(?:franky|frankie)\b[ ,]*\s*)", "", text)
    for _ in range(3):
        text = re.sub(r"^(?:please |(?:can|could|would|will) you )", "", text)
    text = re.sub(r" please$", "", text)
    text = {"turn it up": "volume up", "turn it down": "volume down"}.get(text, text)
    target = r"(?:the |my |your )?(?P<target>volume|(?:screen |display )?brightness)"
    query = re.fullmatch(r"(?:what is|what's|tell me|what is the current|what's the current) " + target + r"(?: level)?", text)
    if query:
        return {"target": "brightness" if "brightness" in query['target'] else "volume", "mode": "query", "value": 0}
    match = re.fullmatch(r"(?P<verb>increase|raise|decrease|reduce|lower) " + target + r"(?: (?:by )?(?P<amount>.+))?", text)
    if not match:
        match = re.fullmatch(r"(?:turn )?" + target + r" (?P<verb>up|down)(?: (?:by )?(?P<amount>.+))?", text)
    if not match:
        match = re.fullmatch(r"(?P<verb>set|turn|change) " + target + r" to (?P<amount>.+)", text)
    if match:
        amount = percentage(match['amount']) if match['amount'] else 10
        if amount is None:
            return {"error": "Please use a whole percentage from zero to one hundred."}
        verb = match['verb']
        return {"target": "brightness" if "brightness" in match['target'] else "volume",
                "mode": "set" if verb in ("set", "turn", "change") else "delta",
                "value": -amount if verb in ("decrease", "reduce", "lower", "down") else amount}
    match = re.fullmatch(r"(?:make (?:it|the screen|the display) )?(?P<verb>louder|quieter|softer|brighter|dimmer)(?: (?:by )?(?P<amount>.+))?", text)
    if match:
        amount = percentage(match['amount']) if match['amount'] else 10
        if amount is None:
            return {"error": "Please use a whole percentage from zero to one hundred."}
        return {"target": "brightness" if match['verb'] in ("brighter", "dimmer") else "volume",
                "mode": "delta", "value": -amount if match['verb'] in ("quieter", "softer", "dimmer") else amount}
    return None
