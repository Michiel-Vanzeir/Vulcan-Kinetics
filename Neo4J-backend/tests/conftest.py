"""Make the backend root (app/, expertise_filter.py) importable from tests/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
