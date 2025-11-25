from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from domains.location.domain.entities import NormalizedSite
from domains.location.domain.value_objects import PickupCategory, StoreCategory


@dataclass(frozen=True)
class StoreCategoryPattern:
    category: StoreCategory
    keywords: tuple[str, ...]
    exclude_if_contains: tuple[str, ...] = ()


STORE_CATEGORY_PATTERNS: tuple[StoreCategoryPattern, ...] = (
    StoreCategoryPattern(
        StoreCategory.REFILL_ZERO,
        (
            "제로웨이스트",
            "리필",
            "무포장",
            "용기",
            "리필스테이션",
            "리필샵",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.CAFE_BAKERY,
        (
            "카페",
            "커피",
            "tea",
            "베이커리",
            "브루어리",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.VEGAN_DINING,
        (
            "비건",
            "vegan",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.UPCYCLE_RECYCLE,
        (
            "되살림",
            "업사이클",
            "리사이클",
            "재활용",
            "수거",
            "리폼",
            "수선",
            "재사용",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.BOOK_WORKSHOP,
        (
            "책방",
            "서점",
            "도서관",
            "공방",
            "스튜디오",
            "갤러리",
            "센터",
            "학교",
            "교육",
            "클래스",
            "워크샵",
            "아카데미",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.MARKET_MART,
        (
            "마트",
            "마켓",
            "시장",
            "생협",
            "coop",
            "co-op",
            "한살림",
            "아이쿱",
            "하나로",
            "공동구매",
            "무인상점",
        ),
    ),
    StoreCategoryPattern(
        StoreCategory.LODGING,
        (
            "숙소",
            "게스트하우스",
            "게하",
            "민박",
            "호텔",
            "펜션",
            "호스텔",
            " stay",
            " 스테이",
            "guesthouse",
            "guest house",
        ),
        exclude_if_contains=("스테이션",),
    ),
)


PICKUP_KEYWORDS: list[tuple[PickupCategory, tuple[str, ...]]] = [
    (PickupCategory.CLEAR_PET, ("무색", "clear", "pet only", "무색페트")),
    (PickupCategory.COLORED_PET, ("유색", "colored", "유색페트")),
    (PickupCategory.CAN, ("캔", "aluminum", "철캔", "metal")),
    (PickupCategory.PAPER, ("종이", "paper", "박스")),
    (PickupCategory.PLASTIC, ("플라스틱", "plastic", "pp", "pe")),
    (PickupCategory.GLASS, ("유리", "glass")),
    (PickupCategory.TEXTILE, ("의류", "섬유", "textile")),
    (PickupCategory.ELECTRONICS, ("전자", "e-waste", "electronic")),
]


def classify_categories(
    site: NormalizedSite,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[StoreCategory, list[PickupCategory]]:
    meta = metadata or site.metadata
    store_category = _classify_store_category(site, meta)
    pickup_categories = _classify_pickup_categories(meta)
    return store_category, pickup_categories


def _classify_store_category(
    site: NormalizedSite,
    meta: Mapping[str, Any],
) -> StoreCategory:
    text_sources = [
        site.positn_intdc_cn,
        site.positn_nm,
        site.positn_pstn_add_expln,
        site.positn_lotno_addr,
        site.positn_rdnm_addr,
        meta.get("memo"),
        meta.get("display1"),
        meta.get("display2"),
    ]
    text = " ".join(value.lower() for value in text_sources if value)
    for pattern in STORE_CATEGORY_PATTERNS:
        if any(keyword in text for keyword in pattern.keywords):
            if any(exclusion in text for exclusion in pattern.exclude_if_contains):
                continue
            return pattern.category

    if "무인" in text or "수거함" in text:
        return StoreCategory.PUBLIC_DROPBOX
    return StoreCategory.GENERAL


def _classify_pickup_categories(meta: Mapping[str, Any]) -> list[PickupCategory]:
    text_sources: Sequence[str | None] = (
        meta.get("clctItemCn"),
        meta.get("etcMttrCn"),
    )
    text = " ".join(value.lower() for value in text_sources if value)
    categories: set[PickupCategory] = set()
    for category, keywords in PICKUP_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            categories.add(category)

    if not categories:
        categories.add(PickupCategory.GENERAL)
    return list(categories)
