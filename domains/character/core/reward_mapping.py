from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import yaml

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "character_reward_mapping.yaml"


@dataclass(frozen=True)
class CharacterCategory:
    major: str
    middle: str
    minor: str | None = None


@dataclass(frozen=True)
class CharacterReward:
    name: str
    categories: tuple[CharacterCategory, ...]
    default_reward: bool = False


def _normalize_string(value: str) -> str:
    return value.strip()


def _load_yaml() -> dict:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Character reward mapping file not found: {DATA_FILE}")
    with DATA_FILE.open("r", encoding="utf-8") as file_obj:
        return yaml.safe_load(file_obj) or {}


@lru_cache(maxsize=1)
def load_reward_mappings() -> tuple[CharacterReward, ...]:
    payload = _load_yaml()
    characters: list[CharacterReward] = []
    for entry in payload.get("characters", []):
        categories_data = entry.get("categories", []) or []
        categories: list[CharacterCategory] = []
        for category in categories_data:
            categories.append(
                CharacterCategory(
                    major=_normalize_string(category["major"]),
                    middle=_normalize_string(category["middle"]),
                    minor=_normalize_string(category["minor"]) if category.get("minor") else None,
                )
            )
        characters.append(
            CharacterReward(
                name=entry["name"],
                categories=tuple(categories),
                default_reward=bool(entry.get("default_reward")),
            )
        )
    return tuple(characters)


def find_matching_characters(
    *,
    major: str,
    middle: str,
    minor: str | None,
) -> list[CharacterReward]:
    major = _normalize_string(major)
    middle = _normalize_string(middle)
    minor = _normalize_string(minor) if minor else None

    matches: list[CharacterReward] = []
    for character in load_reward_mappings():
        for category in character.categories:
            if category.major != major or category.middle != middle:
                continue
            if category.minor and minor and category.minor != minor:
                continue
            if category.minor and not minor:
                continue
            matches.append(character)
            break
    return matches


def get_default_reward() -> CharacterReward | None:
    for character in load_reward_mappings():
        if character.default_reward:
            return character
    return None


def summarize_mapping() -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for character in load_reward_mappings():
        if not character.categories:
            summary.append(
                {
                    "character": character.name,
                    "major": "*",
                    "middle": "*",
                    "minor": character.default_reward and "(default)" or "",
                }
            )
            continue
        for category in character.categories:
            summary.append(
                {
                    "character": character.name,
                    "major": category.major,
                    "middle": category.middle,
                    "minor": category.minor or "*",
                }
            )
    return summary
