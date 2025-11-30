"""My API endpoint modules."""

from . import characters, health, metrics, profile  # noqa: F401

__all__ = ["health", "metrics", "profile", "characters"]
