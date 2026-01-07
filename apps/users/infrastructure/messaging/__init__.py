"""Messaging Infrastructure."""

from users.infrastructure.messaging.default_character_publisher_celery import (
    CeleryDefaultCharacterPublisher,
)

__all__ = ["CeleryDefaultCharacterPublisher"]
