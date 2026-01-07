"""HTTP Error Handling."""

from auth.presentation.http.errors.handlers import register_exception_handlers
from auth.presentation.http.errors.translators import translate_domain_error

__all__ = ["register_exception_handlers", "translate_domain_error"]
