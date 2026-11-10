"""Exact, local-only interaction phrases. Never consult a chat provider."""
import re


def normalized(text: str) -> str:
    return ' '.join(re.sub(r'[^a-z0-9\s]', ' ', text.lower()).split())


def is_wake(text: str) -> bool:
    return normalized(text) in {'hello franky', 'hello frankie', 'hey franky', 'hey frankie'}


def is_pause(text: str) -> bool:
    return re.fullmatch(r'(?:(?:franky|frankie) )?(?:stop listening|pause listening|go to sleep)(?: please)?', normalized(text)) is not None


def is_goodbye(text: str) -> bool:
    # A standalone thank-you ends the turn. Do not discard a new question
    # just because it begins with "thanks".
    return re.fullmatch(r'(?:(?:franky|frankie) )?(?:thank you(?: (?:very|so) much)?|thanks(?: a lot)?)(?: (?:franky|frankie))?', normalized(text)) is not None
