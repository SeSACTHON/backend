"""
Pydantic 모델 정의: Info 도메인에서 사용하는 응답/요청 DTO.

간단한 모킹 데이터만 반환하므로 필드는 최소 구성으로 정의했다.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecycleItem(BaseModel):
    id: int
    name: str
    category: str
    subcategory: Optional[str] = None
    disposal_method: str
    notes: list[str] = Field(default_factory=list)
    recyclable: bool = True


class RecycleCategory(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    item_count: Optional[int] = None


class RecycleSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None


class RegionalRule(BaseModel):
    region: str
    rules: list[str] = Field(default_factory=list)


class FAQEntry(BaseModel):
    id: int
    question: str
    answer: str
    category: str
