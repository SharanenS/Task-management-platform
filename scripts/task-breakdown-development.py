"""Apply S11 only with explicit runtime and migration approval."""

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "calendar_operations", ROOT / "scripts/calendar-development.py"
)
calendar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "up", "status"))
    parser.add_argument("--apply-migration", action="store_true")
    args = parser.parse_args()
    if args.action == "status":
        return calendar.compose("ps").returncode
    calendar.preflight()
    if args.action == "preflight":
        return 0
    if not args.apply_migration:
        raise RuntimeError("migration_approval_required")
    for service in ("people", "project-work", "gateway", "web"):
        if calendar.compose("build", service).returncode:
            return 1
    for arguments in (
        ("up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "project-work-db"),
        ("up", "-d", "--no-deps", "project-work"),
        ("exec", "-T", "project-work", "alembic", "upgrade", "head"),
        (
            "up",
            "-d",
            "--no-deps",
            "--wait",
            "--wait-timeout",
            "180",
            "people",
            "project-work",
            "gateway",
            "web",
        ),
    ):
        if calendar.compose(*arguments).returncode:
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("Task planning operation failed; private details omitted.", file=sys.stderr)
        sys.exit(1)
