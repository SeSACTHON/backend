from pathlib import Path
import sys

# Ensure repo root is on sys.path so `domains._shared` imports work when
# PYTHONPATH points only to `domains/scan`.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
