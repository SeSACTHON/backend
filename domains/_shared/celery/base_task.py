"""
Base Task Classes with Retry Logic, Tracing, and Error Handling
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from celery import Task

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """Base task with retry logic and structured logging."""

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 120  # 최대 2분
    retry_jitter = True
    max_retries = 3

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called when task succeeds."""
        logger.info(
            "Task completed successfully",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "result_type": type(retval).__name__,
            },
        )

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task fails after all retries."""
        logger.error(
            "Task failed after all retries",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "task_args": args,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task is being retried."""
        logger.warning(
            "Task retrying",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "retry_count": self.request.retries,
                "max_retries": self.max_retries,
                "error": str(exc),
            },
        )


class WebhookTask(BaseTask):
    """Task that sends results via webhook callback."""

    abstract = True

    def send_webhook(
        self,
        callback_url: str,
        payload: dict[str, Any],
        *,
        timeout: float = 10.0,
    ) -> bool:
        """Send result to callback URL.

        Args:
            callback_url: URL to send the result to
            payload: JSON payload to send
            timeout: Request timeout in seconds

        Returns:
            True if webhook was sent successfully
        """
        if not callback_url:
            logger.warning("No callback URL provided, skipping webhook")
            return False

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(
                    "Webhook sent successfully",
                    extra={
                        "callback_url": callback_url,
                        "status_code": response.status_code,
                        "task_id": self.request.id,
                    },
                )
                return True
        except httpx.HTTPStatusError as e:
            logger.error(
                "Webhook failed with HTTP error",
                extra={
                    "callback_url": callback_url,
                    "status_code": e.response.status_code,
                    "task_id": self.request.id,
                    "error": str(e),
                },
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                "Webhook request failed",
                extra={
                    "callback_url": callback_url,
                    "task_id": self.request.id,
                    "error": str(e),
                },
            )
            return False

    def send_failure_webhook(
        self,
        callback_url: str,
        task_id: str,
        error: str,
        error_code: str = "TASK_FAILED",
    ) -> bool:
        """Send failure notification to callback URL."""
        payload = {
            "task_id": task_id,
            "status": "failed",
            "error": error,
            "error_code": error_code,
        }
        return self.send_webhook(callback_url, payload)
