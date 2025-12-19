"""Pytest fixtures for Scan service tests."""

import sys
from pathlib import Path

# Add project paths for imports
SERVICE_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
for path in (SERVICE_ROOT, DOMAIN_ROOT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
