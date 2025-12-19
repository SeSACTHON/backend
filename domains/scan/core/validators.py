"""Image URL validation with SSRF prevention."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from domains.scan.core.config import Settings

logger = logging.getLogger(__name__)


class ImageUrlError(str, Enum):
    """이미지 URL 검증 에러 코드."""

    HTTPS_REQUIRED = "HTTPS_REQUIRED"
    INVALID_HOST = "INVALID_HOST"
    INVALID_CHANNEL = "INVALID_CHANNEL"
    INVALID_PATH_FORMAT = "INVALID_PATH_FORMAT"
    INVALID_FILENAME = "INVALID_FILENAME"
    INVALID_EXTENSION = "INVALID_EXTENSION"
    SSRF_BLOCKED = "SSRF_BLOCKED"


@dataclass
class ValidationResult:
    """URL 검증 결과."""

    valid: bool
    error: ImageUrlError | None = None
    message: str | None = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def fail(cls, error: ImageUrlError, message: str) -> "ValidationResult":
        return cls(valid=False, error=error, message=message)


class ImageUrlValidator:
    """
    이미지 URL 검증기.

    검증 순서:
    1. HTTPS 스키마 확인
    2. Allowlist 도메인 확인
    3. SSRF 방지 (프라이빗 IP 차단)
    4. 경로 형식 확인 (/{channel}/{filename}.{ext})
    5. 채널 허용 여부
    6. 파일명 패턴 (UUID hex)
    7. 확장자 허용 여부
    """

    def __init__(self, settings: Settings) -> None:
        self.allowed_hosts = settings.allowed_image_hosts
        self.allowed_channels = settings.allowed_image_channels
        self.allowed_extensions = settings.allowed_image_extensions
        self.filename_pattern = re.compile(settings.image_filename_pattern)

    def validate(self, url: str) -> ValidationResult:
        """
        이미지 URL 전체 검증.

        Args:
            url: 검증할 이미지 URL

        Returns:
            ValidationResult: 검증 결과
        """
        # 1. URL 파싱
        try:
            parsed = urlparse(url)
        except Exception:
            return ValidationResult.fail(
                ImageUrlError.INVALID_PATH_FORMAT,
                "URL 파싱 실패",
            )

        # 2. HTTPS 스키마
        if parsed.scheme != "https":
            return ValidationResult.fail(
                ImageUrlError.HTTPS_REQUIRED,
                f"HTTPS가 필요합니다 (현재: {parsed.scheme})",
            )

        # 3. 도메인 Allowlist
        if parsed.hostname not in self.allowed_hosts:
            logger.warning(
                "Blocked image URL: invalid host",
                extra={"url": url, "host": parsed.hostname},
            )
            return ValidationResult.fail(
                ImageUrlError.INVALID_HOST,
                f"허용되지 않은 호스트: {parsed.hostname}",
            )

        # 4. SSRF 방지
        ssrf_result = self._check_ssrf(parsed.hostname)
        if not ssrf_result.valid:
            return ssrf_result

        # 5. 경로 형식 검증
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 2:
            return ValidationResult.fail(
                ImageUrlError.INVALID_PATH_FORMAT,
                f"경로 형식 오류: /{'/'.join(path_parts)} (예상: /channel/filename.ext)",
            )

        channel, filename_with_ext = path_parts

        # 6. 채널 검증
        if channel not in self.allowed_channels:
            return ValidationResult.fail(
                ImageUrlError.INVALID_CHANNEL,
                f"허용되지 않은 채널: {channel}",
            )

        # 7. 파일명 분리
        dot_idx = filename_with_ext.rfind(".")
        if dot_idx == -1:
            return ValidationResult.fail(
                ImageUrlError.INVALID_EXTENSION,
                "확장자가 없습니다",
            )

        filename = filename_with_ext[:dot_idx]
        extension = filename_with_ext[dot_idx:].lower()

        # 8. 확장자 검증
        if extension not in self.allowed_extensions:
            return ValidationResult.fail(
                ImageUrlError.INVALID_EXTENSION,
                f"허용되지 않은 확장자: {extension}",
            )

        # 9. 파일명 패턴 검증 (UUID hex)
        if not self.filename_pattern.match(filename):
            return ValidationResult.fail(
                ImageUrlError.INVALID_FILENAME,
                f"파일명 형식 오류: {filename}",
            )

        return ValidationResult.ok()

    def _check_ssrf(self, hostname: str | None) -> ValidationResult:
        """SSRF 방지: 프라이빗/내부 IP 차단."""
        if hostname is None:
            return ValidationResult.fail(
                ImageUrlError.SSRF_BLOCKED,
                "호스트명이 없습니다",
            )

        # 위험한 호스트명 직접 차단
        dangerous_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
        if hostname.lower() in dangerous_hosts:
            logger.warning("SSRF blocked: dangerous host", extra={"host": hostname})
            return ValidationResult.fail(
                ImageUrlError.SSRF_BLOCKED,
                "내부 호스트 접근 차단됨",
            )

        # DNS 확인 후 IP 검증
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)

            if ip.is_private:
                logger.warning(
                    "SSRF blocked: private IP",
                    extra={"host": hostname, "ip": ip_str},
                )
                return ValidationResult.fail(
                    ImageUrlError.SSRF_BLOCKED,
                    "프라이빗 IP 접근 차단됨",
                )

            if ip.is_loopback:
                logger.warning(
                    "SSRF blocked: loopback",
                    extra={"host": hostname, "ip": ip_str},
                )
                return ValidationResult.fail(
                    ImageUrlError.SSRF_BLOCKED,
                    "루프백 주소 접근 차단됨",
                )

            if ip.is_reserved:
                logger.warning(
                    "SSRF blocked: reserved IP",
                    extra={"host": hostname, "ip": ip_str},
                )
                return ValidationResult.fail(
                    ImageUrlError.SSRF_BLOCKED,
                    "예약된 IP 접근 차단됨",
                )

        except socket.gaierror:
            # DNS 실패 - Allowlist에서 이미 걸러졌으므로 통과
            # (CDN 도메인이 일시적으로 해석 안 될 수 있음)
            pass
        except ValueError:
            # IP 파싱 실패 - IPv6 등
            pass

        return ValidationResult.ok()
