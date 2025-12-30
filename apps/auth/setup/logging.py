"""Logging Configuration."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """로깅 설정."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
