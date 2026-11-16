"""Run only a rollback-scoped verification in the owned S2 people service."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "account_entry", ROOT / "scripts/account-entry-development.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.preflight()
    result = module.compose(
        "exec",
        "-T",
        "people",
        "python",
        "-c",
        (ROOT / "tests/account_entry/postgres_check.py").read_text(encoding="utf-8"),
        capture=True,
    )
    if result.returncode:
        print(
            "Scoped PostgreSQL verification failed. Private diagnostics omitted.", file=sys.stderr
        )
        sys.exit(1)
    print("PostgreSQL schema constraints and scoped rollback verified.")
