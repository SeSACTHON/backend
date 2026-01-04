"""Pickup Category Enum."""

from enum import Enum


class PickupCategory(str, Enum):
    """수거 품목 카테고리."""

    CLEAR_PET = "clear_pet"
    COLORED_PET = "colored_pet"
    CAN = "can"
    PAPER = "paper"
    PLASTIC = "plastic"
    GLASS = "glass"
    TEXTILE = "textile"
    ELECTRONICS = "electronics"
    GENERAL = "general"
