from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from services._shared.security import TokenPayload, build_access_token_dependency


access_token_dependency = build_access_token_dependency(get_settings, cookie_alias="s_access")
CurrentUser = Annotated[TokenPayload, Depends(access_token_dependency)]

__all__ = ["CurrentUser", "access_token_dependency"]
