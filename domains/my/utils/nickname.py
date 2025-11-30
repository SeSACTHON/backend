from __future__ import annotations

import secrets

_ADJECTIVES = [
    "초록",
    "맑은",
    "푸른",
    "따뜻한",
    "빛나는",
    "싱그러운",
    "잔잔한",
    "깨끗한",
    "산뜻한",
    "포근한",
]

_NOUNS = [
    "씨앗",
    "숲지기",
    "바람",
    "별빛",
    "이코",
    "물결",
    "햇살",
    "나뭇잎",
    "자연",
    "지구친구",
]

_rng = secrets.SystemRandom()


def generate_default_nickname() -> str:
    """Build a friendly eco-themed nickname such as '초록이코42'."""
    prefix = _rng.choice(_ADJECTIVES)
    suffix = _rng.choice(_NOUNS)
    number = _rng.randrange(10, 100)
    return f"{prefix}{suffix}{number}"
