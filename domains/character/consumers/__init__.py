"""Character domain MQ consumers."""

from domains.character.consumers.reward import (
    celery_app,
    persist_reward_task,
    reward_consumer_task,
    scan_reward_task,
)
from domains.character.consumers.sync_my import sync_to_my_task

__all__ = [
    "celery_app",
    "persist_reward_task",
    "reward_consumer_task",
    "scan_reward_task",
    "sync_to_my_task",
]
