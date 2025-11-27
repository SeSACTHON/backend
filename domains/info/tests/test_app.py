import importlib
import sys
from pathlib import Path

from fastapi import FastAPI

MODULE_CANDIDATES = (
    "domains.info.main",
    "info.main",
    "main",
)

PATHS_TO_ADD = (
    Path(__file__).resolve().parents[1],  # domains/info
    Path(__file__).resolve().parents[2],  # domains
    Path(__file__).resolve().parents[3],  # repo root (/backend)
    Path(__file__).resolve().parents[4],  # workspace root
)
for extra_path in PATHS_TO_ADD:
    resolved = str(extra_path)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def load_fastapi_app() -> FastAPI:
    last_exc: ModuleNotFoundError | None = None
    for module_name in MODULE_CANDIDATES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            last_exc = exc
            continue
        app = getattr(module, "app", None)
        if isinstance(app, FastAPI):
            return app
    message = "FastAPI application instance not found"
    if last_exc:
        raise AssertionError(message) from last_exc
    raise AssertionError(message)


def test_fastapi_app_instantiates():
    app = load_fastapi_app()
    assert isinstance(app, FastAPI)
