"""Fetch News Command.

뉴스 조회 UseCase.
캐시 확인 → 미스 시 API 호출 → 결과 반환.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from info.application.dto.news_request import NewsListRequest
from info.application.dto.news_response import (
    NewsArticleResponse,
    NewsListResponse,
    NewsMeta,
)

if TYPE_CHECKING:
    from info.application.ports.news_cache import NewsCachePort
    from info.application.ports.news_source import NewsSourcePort
    from info.application.services.news_aggregator import NewsAggregatorService
    from info.infrastructure.integrations.og.og_image_extractor import OGImageExtractor

logger = logging.getLogger(__name__)


class FetchNewsCommand:
    """뉴스 조회 Command (UseCase).

    플로우:
    1. 캐시 확인 (is_fresh)
    2. 캐시 미스 → 외부 API 병렬 호출
    3. 결과 병합/분류/캐싱
    4. Cursor 기반 페이지네이션 적용
    5. 응답 반환
    """

    def __init__(
        self,
        news_sources: list[NewsSourcePort],
        news_cache: NewsCachePort,
        aggregator: NewsAggregatorService,
        cache_ttl: int = 3600,
        og_extractor: OGImageExtractor | None = None,
    ):
        """초기화.

        Args:
            news_sources: 뉴스 소스 목록 (네이버, NewsData 등)
            news_cache: 뉴스 캐시
            aggregator: 뉴스 집계 서비스
            cache_ttl: 캐시 TTL (초)
            og_extractor: OG 이미지 추출기 (이미지 없는 기사 보강)
        """
        self._news_sources = news_sources
        self._news_cache = news_cache
        self._aggregator = aggregator
        self._cache_ttl = cache_ttl
        self._og_extractor = og_extractor

    async def execute(self, request: NewsListRequest) -> NewsListResponse:
        """Command 실행.

        Args:
            request: 뉴스 목록 요청

        Returns:
            뉴스 목록 응답
        """
        category = request.category

        # 1. 캐시 확인
        is_fresh = await self._news_cache.is_fresh(category)

        if not is_fresh:
            # 2. 캐시 미스 → 외부 API 호출 및 캐싱
            await self._refresh_cache(category)

        # 3. 캐시에서 페이지네이션 조회
        articles, next_cursor, has_more = await self._news_cache.get_articles(
            category=category,
            cursor=request.cursor,
            limit=request.limit,
        )

        # 4. 소스 필터링 (요청된 경우)
        if request.source != "all":
            articles = [a for a in articles if a.source == request.source]

        # 5. 이미지 필터링 (요청된 경우)
        if request.has_image:
            articles = [a for a in articles if a.thumbnail_url]

        # 6. 메타 정보 조회
        total_cached = await self._news_cache.get_total_count(category)
        cache_ttl = await self._news_cache.get_ttl(category)

        # 7. 응답 생성
        return NewsListResponse(
            articles=[NewsArticleResponse.from_entity(a) for a in articles],
            next_cursor=str(next_cursor) if next_cursor else None,
            has_more=has_more,
            meta=NewsMeta(
                total_cached=total_cached,
                cache_expires_in=cache_ttl,
            ),
        )

    async def _refresh_cache(self, category: str) -> None:
        """캐시 갱신 (외부 API 호출).

        Args:
            category: 카테고리
        """
        logger.info("Refreshing news cache", extra={"category": category})

        # 검색 쿼리 생성
        queries = self._aggregator.get_search_queries(category)

        # 모든 소스에서 병렬로 뉴스 가져오기
        all_articles = []

        for query in queries:
            tasks = [
                source.fetch_news(query=query, max_results=30)
                for source in self._news_sources
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning("News source failed: %s", result)
                    continue
                all_articles.extend(result)

        if not all_articles:
            logger.warning("No articles fetched from any source")
            return

        # 병합 및 중복 제거
        unique_articles = self._aggregator.merge_and_deduplicate(all_articles)

        # 카테고리 분류
        classified_articles = self._aggregator.classify_articles(unique_articles)

        # OG 이미지 추출 (이미지 없는 기사 보강)
        if self._og_extractor:
            classified_articles = await self._og_extractor.enrich_articles_with_images(
                classified_articles
            )

        # 이미지 있는 기사 우선 정렬 (Perplexity UI 최적화)
        prioritized_articles = self._aggregator.prioritize_with_images(classified_articles)

        # "all" 카테고리에 전체 저장
        await self._news_cache.set_articles(
            category="all",
            articles=prioritized_articles,
            ttl=self._cache_ttl,
        )

        # 개별 카테고리에도 저장
        if category != "all":
            filtered = self._aggregator.filter_by_category(
                prioritized_articles, category
            )
            await self._news_cache.set_articles(
                category=category,
                articles=filtered,
                ttl=self._cache_ttl,
            )

        # 이미지 통계
        with_images = sum(1 for a in prioritized_articles if a.thumbnail_url)

        logger.info(
            "News cache refreshed",
            extra={
                "category": category,
                "total_articles": len(prioritized_articles),
                "with_images": with_images,
                "without_images": len(prioritized_articles) - with_images,
            },
        )
