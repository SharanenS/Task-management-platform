"""Run only after S8 runtime approval; preserve fixed, credential-free diagnostics."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    spec = importlib.util.spec_from_file_location(
        "calendar_operations", ROOT / "scripts/calendar-development.py"
    )
    calendar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calendar)
    calendar.preflight()
    result = calendar.compose(
        "exec",
        "-T",
        "project-work",
        "python",
        "-c",
        (ROOT / "tests/projects/membership_postgres_check.py").read_text(encoding="utf-8"),
        capture=True,
    )
    records = []
    for line in result.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("kind") in {"failure", "cleanup", "passed"}:
            records.append(row)
    report = ROOT / "test-results/reports/s8/postgres.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if (
        result.returncode
        or not any(r.get("kind") == "passed" for r in records)
        or not any(r.get("kind") == "cleanup" and r.get("verified") is True for r in records)
    ):
        print(
            "Membership PostgreSQL verification failed; sanitized boundaries saved.",
            file=sys.stderr,
        )
        return 1
    print(
        "Membership PostgreSQL schema, competing leader changes, replay, history "
        "and owned cleanup verified."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print(
            "Membership PostgreSQL verification failed; private details omitted.", file=sys.stderr
        )
        sys.exit(1)
