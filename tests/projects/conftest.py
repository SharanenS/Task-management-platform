import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for name in ("services/project-work", "packages/security", "services/gateway"):
    sys.path.insert(0, str(ROOT / name))
