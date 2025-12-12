import logging
from typing import Optional

from envoy.service.auth.v3 import external_auth_pb2
from envoy.service.auth.v3 import external_auth_pb2_grpc
from envoy.type.v3 import http_status_pb2
from google.rpc import code_pb2, status_pb2
from redis.asyncio import Redis

from domains.auth.core.config import get_settings
from domains.auth.core.jwt import decode_jwt
from domains.auth.services.token_blacklist import TokenBlacklist

logger = logging.getLogger(__name__)


class AuthorizationServicer(external_auth_pb2_grpc.AuthorizationServicer):
    """
    gRPC Interface Layer for Envoy External Authorization.
    Verifies JWT tokens and checks against the blacklist.
    """

    def __init__(self, redis_client: Redis):
        # Inject redis client directly into TokenBlacklist
        self.blacklist_service = TokenBlacklist(redis_client)
        self.settings = get_settings()

    async def Check(self, request, context):
        """
        Envoy External Authorization Check implementation.
        1. Extract Bearer Token
        2. Verify JWT (Signature, Expiration)
        3. Check Blacklist (Redis)
        4. Allow/Deny
        """
        try:
            # 1. Request Parsing
            headers = request.attributes.request.http.headers
            auth_header = headers.get("authorization", "")
            token = self._extract_token(auth_header)

            if not token:
                return self._deny_request(
                    "Missing or invalid Authorization header", http_status_pb2.Unauthorized
                )

            # 2. Verify JWT
            try:
                payload = decode_jwt(
                    token,
                    secret=self.settings.secret_key,
                    algorithm=self.settings.algorithm,
                    audience="sesacthon-clients",  # Adjust if needed
                    issuer="sesacthon-auth",  # Adjust if needed
                )
            except Exception as e:
                logger.warning(f"[gRPC] Invalid token: {e}")
                return self._deny_request("Invalid token", http_status_pb2.Unauthorized)

            # 3. Check Blacklist
            try:
                is_blacklisted = await self.blacklist_service.contains(payload.jti)
                if is_blacklisted:
                    logger.warning(f"[gRPC] Token blacklisted: {payload.jti}")
                    return self._deny_request("Token is blacklisted", http_status_pb2.Forbidden)
            except Exception as e:
                logger.error(f"[gRPC] Redis error checking blacklist: {e}")
                # Fail-closed: If we can't check blacklist, deny access for security
                return self._deny_request(
                    "Internal Authorization Error", http_status_pb2.InternalServerError
                )

            # 4. Allow Request
            # Optionally add headers (e.g., x-user-id) to upstream
            return self._allow_request(user_id=str(payload.sub))

        except Exception as e:
            logger.exception(f"[gRPC] Unexpected error in Check: {e}")
            return self._deny_request("Internal Server Error", http_status_pb2.InternalServerError)

    def _extract_token(self, auth_header: str) -> Optional[str]:
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        parts = auth_header.split(" ")
        if len(parts) != 2:
            return None
        return parts[1]

    def _allow_request(self, user_id: str):
        return external_auth_pb2.CheckResponse(
            status=status_pb2.Status(code=code_pb2.OK),
            ok_response=external_auth_pb2.OkHttpResponse(
                headers=[
                    # Pass verified user ID to upstream services
                    external_auth_pb2.HeaderValueOption(
                        header=external_auth_pb2.HeaderValue(key="x-user-id", value=user_id)
                    )
                ]
            ),
        )

    def _deny_request(self, message: str, status_code: int):
        return external_auth_pb2.CheckResponse(
            status=status_pb2.Status(code=code_pb2.PERMISSION_DENIED, message=message),
            denied_response=external_auth_pb2.DeniedHttpResponse(
                status=http_status_pb2.HttpStatus(code=status_code),
                body=message,
            ),
        )
