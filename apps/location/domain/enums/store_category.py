"""Store Category Enum."""

from enum import Enum


class StoreCategory(str, Enum):
    """매장 카테고리."""

    REFILL_ZERO = "refill_zero"
    CAFE_BAKERY = "cafe_bakery"
    VEGAN_DINING = "vegan_dining"
    UPCYCLE_RECYCLE = "upcycle_recycle"
    BOOK_WORKSHOP = "book_workshop"
    MARKET_MART = "market_mart"
    LODGING = "lodging"
    PUBLIC_DROPBOX = "public_dropbox"
    GENERAL = "general"
