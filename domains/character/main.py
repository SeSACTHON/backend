"""Compatibility module exposing the FastAPI app entrypoint."""

from domains.character.app.main import app, create_app

__all__ = ["app", "create_app"]
