"""Bulk Waste Service.

대형폐기물 관련 순수 비즈니스 로직 (Port 의존 없음).

Clean Architecture:
- Service: 이 파일 - 순수 비즈니스 로직, Port 의존 없음
- Command: search_bulk_waste_command.py - Port 호출 + 오케스트레이션
- Port: BulkWasteClientPort - HTTP API 호출
- Node: bulk_waste_node.py - LangGraph glue
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chat_worker.application.ports.bulk_waste_client import (
        BulkWasteCollectionDTO,
        BulkWasteItemDTO,
        WasteDisposalInfoDTO,
    )


class BulkWasteService:
    """대형폐기물 관련 순수 비즈니스 로직.

    모든 메서드는 static/class method로 Port 의존 없이 구현.
    Command에서 호출하여 사용.
    """

    @staticmethod
    def extract_sigungu(user_location: dict[str, Any] | None) -> str | None:
        """사용자 위치에서 시군구 추출.

        Args:
            user_location: 사용자 위치 정보 딕셔너리

        Returns:
            시군구명 또는 None
        """
        if not user_location:
            return None

        # 주소 정보에서 시군구 추출
        address = user_location.get("address", {})
        if isinstance(address, dict):
            sigungu = address.get("sigungu") or address.get("구")
            if sigungu:
                return sigungu

        # 직접 sigungu 필드가 있는 경우
        if user_location.get("sigungu"):
            return user_location["sigungu"]

        return None

    @staticmethod
    def format_disposal_info(info: "WasteDisposalInfoDTO") -> dict[str, Any]:
        """폐기물 배출 정보를 응답 컨텍스트로 변환.

        Args:
            info: 폐기물 배출 정보 DTO

        Returns:
            LLM 응답 생성용 컨텍스트 딕셔너리
        """
        return {
            "type": "disposal_info",
            "region": info.full_address,
            "general_waste": info.general_waste_method,
            "food_waste": info.food_waste_method,
            "recyclable_schedule": info.recyclable_schedule,
            "bulk_waste": info.bulk_waste_method,
            "contact": info.contact,
            "department": info.management_dept,
        }

    @staticmethod
    def format_bulk_waste_collection(
        collection: "BulkWasteCollectionDTO",
    ) -> dict[str, Any]:
        """대형폐기물 수거 정보를 응답 컨텍스트로 변환.

        Args:
            collection: 대형폐기물 수거 정보 DTO

        Returns:
            LLM 응답 생성용 컨텍스트 딕셔너리
        """
        return {
            "type": "bulk_waste_collection",
            "sigungu": collection.sigungu,
            "application_url": collection.application_url,
            "application_phone": collection.application_phone,
            "collection_method": collection.collection_method,
            "fee_payment_method": collection.fee_payment_method,
        }

    @staticmethod
    def format_bulk_waste_fees(
        items: list["BulkWasteItemDTO"],
        sigungu: str,
    ) -> dict[str, Any]:
        """대형폐기물 수수료 목록을 응답 컨텍스트로 변환.

        Args:
            items: 품목별 수수료 DTO 목록
            sigungu: 시군구명

        Returns:
            LLM 응답 생성용 컨텍스트 딕셔너리
        """
        fee_list = [
            {
                "item_name": item.item_name,
                "category": item.category,
                "fee": item.fee_text,
                "size_info": item.size_info,
                "note": item.note,
            }
            for item in items
        ]

        return {
            "type": "bulk_waste_fees",
            "sigungu": sigungu,
            "items": fee_list,
            "item_count": len(fee_list),
        }

    @staticmethod
    def build_not_found_context(sigungu: str | None = None) -> dict[str, Any]:
        """정보를 찾을 수 없을 때의 컨텍스트.

        Args:
            sigungu: 시군구명

        Returns:
            에러 컨텍스트 딕셔너리
        """
        if sigungu:
            message = (
                f"{sigungu} 지역의 대형폐기물 정보를 찾을 수 없어요. "
                "해당 구청 환경과에 문의하시면 정확한 정보를 얻을 수 있어요."
            )
        else:
            message = (
                "지역 정보가 없어서 대형폐기물 정보를 찾을 수 없어요. "
                "위치를 알려주시거나 구청명을 말씀해주세요."
            )

        return {
            "type": "not_found",
            "message": message,
        }

    @staticmethod
    def build_no_location_context() -> dict[str, Any]:
        """위치 정보가 필요할 때의 컨텍스트.

        Returns:
            HITL 트리거용 컨텍스트 딕셔너리
        """
        return {
            "type": "location_required",
            "message": (
                "대형폐기물 수거 신청 방법은 지역마다 달라요. "
                "어느 지역(구)에서 버리실 건가요?"
            ),
        }

    @staticmethod
    def build_error_context(error_message: str) -> dict[str, Any]:
        """에러 발생 시의 컨텍스트.

        Args:
            error_message: 에러 메시지

        Returns:
            에러 컨텍스트 딕셔너리
        """
        return {
            "type": "error",
            "message": error_message,
        }

    @staticmethod
    def to_answer_context(
        disposal_info: list["WasteDisposalInfoDTO"] | None = None,
        collection_info: "BulkWasteCollectionDTO | None" = None,
        fee_items: list["BulkWasteItemDTO"] | None = None,
        sigungu: str | None = None,
    ) -> dict[str, Any]:
        """통합 응답 컨텍스트 생성.

        Args:
            disposal_info: 배출 정보 목록
            collection_info: 수거 정보
            fee_items: 수수료 정보 목록
            sigungu: 시군구명

        Returns:
            LLM 응답 생성용 통합 컨텍스트
        """
        context: dict[str, Any] = {
            "type": "bulk_waste_info",
            "sigungu": sigungu,
        }

        if disposal_info:
            context["disposal_info"] = [
                BulkWasteService.format_disposal_info(info) for info in disposal_info
            ]

        if collection_info:
            context["collection"] = BulkWasteService.format_bulk_waste_collection(
                collection_info
            )

        if fee_items:
            context["fees"] = BulkWasteService.format_bulk_waste_fees(
                fee_items, sigungu or ""
            )

        return context


__all__ = ["BulkWasteService"]
