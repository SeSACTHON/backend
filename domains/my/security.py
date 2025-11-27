from domains._shared.security import TokenPayload, build_access_token_dependency

from domains.my.core.config import get_settings

access_token_dependency = build_access_token_dependency(
    get_settings,
    cookie_alias=get_settings().access_cookie_name,
)

__all__ = ["access_token_dependency", "TokenPayload"]
