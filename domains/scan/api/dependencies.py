from domains._shared.security import build_access_token_dependency
from domains.scan.core.config import get_settings

settings = get_settings()

access_token_dependency = build_access_token_dependency(
    get_settings,
    cookie_alias=settings.access_cookie_name,
)

__all__ = ["access_token_dependency"]
