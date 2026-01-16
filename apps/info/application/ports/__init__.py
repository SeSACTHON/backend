"""Application Ports (Interfaces)."""

from info.application.ports.news_cache import NewsCachePort
from info.application.ports.news_source import NewsSourcePort

__all__ = ["NewsSourcePort", "NewsCachePort"]
