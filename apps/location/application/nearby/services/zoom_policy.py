"""Zoom Policy Service.

줌 레벨에 따른 검색 반경 및 제한 정책을 결정합니다.
Port 의존성이 없는 순수 로직입니다.
"""

from __future__ import annotations

DEFAULT_RADIUS_METERS = 5000

ZOOM_RADIUS_TABLE = {
    1: 80000,
    2: 60000,
    3: 45000,
    4: 30000,
    5: 20000,
    6: 15000,
    7: 10000,
    8: 8000,
    9: 6000,
    10: 4500,
    11: 3000,
    12: 2000,
    13: 1200,
    14: 800,
    15: 500,
    16: 300,
    17: 200,
    18: 150,
    19: 120,
    20: 100,
}

ZOOM_LIMIT_TABLE = {
    1: 50,
    4: 80,
    7: 120,
    10: 160,
    13: 200,
}

KAKAO_MIN_ZOOM_LEVEL = 1
KAKAO_MAX_ZOOM_LEVEL = 14
_INTERNAL_MIN_ZOOM = min(ZOOM_RADIUS_TABLE)
_INTERNAL_MAX_ZOOM = max(ZOOM_RADIUS_TABLE)
_INTERNAL_ZOOM_SPAN = _INTERNAL_MAX_ZOOM - _INTERNAL_MIN_ZOOM
_KAKAO_ZOOM_SPAN = KAKAO_MAX_ZOOM_LEVEL - KAKAO_MIN_ZOOM_LEVEL


class ZoomPolicyService:
    """줌 정책 서비스.

    카카오맵 줌 레벨을 내부 줌 레벨로 변환하고,
    검색 반경/제한을 결정합니다.
    """

    @staticmethod
    def radius_from_zoom(zoom: int | None) -> int:
        """줌 레벨에 따른 검색 반경(meters)을 반환합니다."""
        if zoom is None:
            return DEFAULT_RADIUS_METERS
        normalized_zoom = ZoomPolicyService._normalize_zoom(zoom)
        return ZOOM_RADIUS_TABLE.get(normalized_zoom, DEFAULT_RADIUS_METERS)

    @staticmethod
    def limit_from_zoom(zoom: int | None) -> int:
        """줌 레벨에 따른 결과 제한 수를 반환합니다."""
        if zoom is None:
            return 200
        normalized_zoom = ZoomPolicyService._normalize_zoom(zoom)
        for level in sorted(ZOOM_LIMIT_TABLE.keys(), reverse=True):
            if normalized_zoom >= level:
                return ZOOM_LIMIT_TABLE[level]
        return 50

    @staticmethod
    def _normalize_zoom(zoom: int) -> int:
        """카카오맵 줌 레벨(1=street, 14=world)을 내부 스케일(1=world, 20=street)로 변환."""
        clamped = max(KAKAO_MIN_ZOOM_LEVEL, min(zoom, KAKAO_MAX_ZOOM_LEVEL))
        if _KAKAO_ZOOM_SPAN == 0 or _INTERNAL_ZOOM_SPAN == 0:
            return _INTERNAL_MAX_ZOOM
        ratio = (KAKAO_MAX_ZOOM_LEVEL - clamped) / _KAKAO_ZOOM_SPAN
        internal_value = _INTERNAL_MIN_ZOOM + int((_INTERNAL_ZOOM_SPAN * ratio) + 0.5)
        return max(_INTERNAL_MIN_ZOOM, min(_INTERNAL_MAX_ZOOM, internal_value))
