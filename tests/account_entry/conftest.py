"""Source-only tests never connect to a development database or identity provider."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for name in ("packages/security", "services/people", "services/gateway", "scripts"):
    sys.path.insert(0, str(ROOT / name))
