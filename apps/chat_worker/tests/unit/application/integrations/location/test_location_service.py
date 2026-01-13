"""LocationService 단위 테스트."""

from __future__ import annotations

import pytest

from chat_worker.application.integrations.location.ports import (
    LocationClientPort,
    LocationDTO,
)
from chat_worker.application.integrations.location.services.location_service import (
    LocationService,
)
from chat_worker.domain import LocationData


class MockLocationClient(LocationClientPort):
    """테스트용 Location Mock."""

    def __init__(self, centers: list[LocationDTO] | None = None):
        self._centers = centers or []
        self._zerowaste: list[LocationDTO] = []
        self.search_recycling_called = False
        self.search_zerowaste_called = False
        self.last_lat: float | None = None
        self.last_lon: float | None = None
        self.last_radius: int | None = None
        self.last_limit: int | None = None

    async def search_recycling_centers(
        self,
        lat: float,
        lon: float,
        radius: int | None = None,
        limit: int = 10,
    ) -> list[LocationDTO]:
        self.search_recycling_called = True
        self.last_lat = lat
        self.last_lon = lon
        self.last_radius = radius
        self.last_limit = limit
        return self._centers

    async def search_zerowaste_shops(
        self,
        lat: float,
        lon: float,
        radius: int = 5000,
        limit: int = 10,
    ) -> list[LocationDTO]:
        self.search_zerowaste_called = True
        self.last_lat = lat
        self.last_lon = lon
        self.last_radius = radius
        self.last_limit = limit
        return self._zerowaste


def create_location_dto(
    id: int = 1,
    name: str = "테스트 센터",
    road_address: str = "서울시 강남구 테스트로 123",
    distance_km: float = 1.5,
    distance_text: str = "1.5km",
    is_open: bool = True,
    phone: str | None = "02-1234-5678",
    pickup_categories: list[str] | None = None,
) -> LocationDTO:
    """LocationDTO 팩토리."""
    return LocationDTO(
        id=id,
        name=name,
        road_address=road_address,
        latitude=37.5665,
        longitude=126.9780,
        distance_km=distance_km,
        distance_text=distance_text,
        store_category="재활용센터",
        pickup_categories=pickup_categories or ["플라스틱", "종이"],
        is_open=is_open,
        phone=phone,
    )


class TestLocationService:
    """LocationService 테스트 스위트."""

    @pytest.fixture
    def sample_centers(self) -> list[LocationDTO]:
        """샘플 센터 목록."""
        return [
            create_location_dto(id=1, name="센터A", distance_km=0.5),
            create_location_dto(id=2, name="센터B", distance_km=1.2),
            create_location_dto(id=3, name="센터C", distance_km=2.0),
        ]

    @pytest.fixture
    def mock_client(self, sample_centers: list[LocationDTO]) -> MockLocationClient:
        """Mock 클라이언트."""
        return MockLocationClient(centers=sample_centers)

    @pytest.fixture
    def service(self, mock_client: MockLocationClient) -> LocationService:
        """테스트용 서비스."""
        return LocationService(mock_client)

    @pytest.fixture
    def user_location(self) -> LocationData:
        """사용자 위치."""
        return LocationData(latitude=37.5665, longitude=126.9780)

    # ==========================================================
    # search_recycling_centers Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_search_recycling_centers(
        self,
        service: LocationService,
        mock_client: MockLocationClient,
        user_location: LocationData,
        sample_centers: list[LocationDTO],
    ):
        """재활용 센터 검색."""
        result = await service.search_recycling_centers(user_location)

        assert len(result) == len(sample_centers)
        assert mock_client.search_recycling_called
        assert mock_client.last_lat == user_location.latitude
        assert mock_client.last_lon == user_location.longitude

    @pytest.mark.asyncio
    async def test_search_recycling_centers_with_params(
        self,
        service: LocationService,
        mock_client: MockLocationClient,
        user_location: LocationData,
    ):
        """파라미터 전달 확인."""
        await service.search_recycling_centers(
            location=user_location,
            radius=3000,
            limit=10,
        )

        assert mock_client.last_radius == 3000
        assert mock_client.last_limit == 10

    @pytest.mark.asyncio
    async def test_search_recycling_centers_empty(
        self,
        user_location: LocationData,
    ):
        """빈 결과."""
        mock_client = MockLocationClient(centers=[])
        service = LocationService(mock_client)

        result = await service.search_recycling_centers(user_location)

        assert result == []

    # ==========================================================
    # search_zerowaste_shops Tests
    # ==========================================================

    @pytest.mark.asyncio
    async def test_search_zerowaste_shops(
        self,
        service: LocationService,
        mock_client: MockLocationClient,
        user_location: LocationData,
    ):
        """제로웨이스트샵 검색."""
        await service.search_zerowaste_shops(user_location)

        assert mock_client.search_zerowaste_called
        assert mock_client.last_lat == user_location.latitude

    # ==========================================================
    # to_answer_context Tests
    # ==========================================================

    def test_to_answer_context_with_centers(
        self,
        sample_centers: list[LocationDTO],
        user_location: LocationData,
    ):
        """센터 있는 경우 컨텍스트."""
        context = LocationService.to_answer_context(
            locations=sample_centers,
            user_location=user_location,
        )

        assert context["found"] is True
        assert context["count"] == 3
        assert "centers" in context
        assert len(context["centers"]) == 3
        assert context["centers"][0]["name"] == "센터A"

    def test_to_answer_context_empty(self):
        """빈 결과 컨텍스트."""
        context = LocationService.to_answer_context(locations=[])

        assert context["found"] is False
        assert context["count"] == 0
        assert "message" in context
        assert "찾지 못했어요" in context["message"]

    def test_to_answer_context_without_user_location(
        self,
        sample_centers: list[LocationDTO],
    ):
        """사용자 위치 없이."""
        context = LocationService.to_answer_context(locations=sample_centers)

        assert "user_location" not in context
        assert context["found"] is True

    def test_to_answer_context_with_user_location(
        self,
        sample_centers: list[LocationDTO],
        user_location: LocationData,
    ):
        """사용자 위치 포함."""
        context = LocationService.to_answer_context(
            locations=sample_centers,
            user_location=user_location,
        )

        assert "user_location" in context
        assert context["user_location"]["latitude"] == user_location.latitude

    def test_to_answer_context_center_structure(self):
        """센터 구조 확인."""
        center = create_location_dto(
            name="테스트센터",
            road_address="테스트주소",
            distance_text="500m",
            is_open=True,
            phone="010-1234-5678",
            pickup_categories=["플라스틱"],
        )

        context = LocationService.to_answer_context([center])

        center_ctx = context["centers"][0]
        assert center_ctx["name"] == "테스트센터"
        assert center_ctx["address"] == "테스트주소"
        assert center_ctx["distance"] == "500m"
        assert center_ctx["is_open"] is True
        assert center_ctx["phone"] == "010-1234-5678"
        assert center_ctx["categories"] == ["플라스틱"]
