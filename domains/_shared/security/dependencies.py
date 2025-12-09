from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException, status

from .jwt import TokenPayload, TokenType, extract_token_payload


def build_access_token_dependency(
    get_settings: Callable,
    *,
    cookie_alias: str = "s_access",
    blacklist_dependency: Optional[type] = None,
):
    """
    Factory that returns a FastAPI dependency for extracting access-token from Authorization header.
    (Assumes token verification is handled by Istio/Gateway)
    """

    if blacklist_dependency is not None:

        async def dependency(
            authorization: Optional[str] = Header(default=None),
            blacklist=Depends(blacklist_dependency),
        ) -> TokenPayload:
            if not authorization:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header"
                )

            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization format"
                )

            # Decode without verification (Istio handled it)
            payload = extract_token_payload(token)

            if payload.type is not TokenType.ACCESS:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Token type mismatch"
                )
            if await blacklist.contains(payload.jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked"
                )
            return payload

        return dependency

    async def dependency(
        authorization: Optional[str] = Header(default=None),
    ) -> TokenPayload:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header"
            )

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization format"
            )

        # Decode without verification
        payload = extract_token_payload(token)

        if payload.type is not TokenType.ACCESS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token type mismatch"
            )
        return payload

    return dependency
