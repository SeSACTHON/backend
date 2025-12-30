"""Auth Event Consumers."""

from apps.auth.workers.consumers.blacklist_relay import BlacklistRelay

__all__ = ["BlacklistRelay"]
