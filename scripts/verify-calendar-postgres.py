"""Verify only the owned S6 database through its scoped runtime wrapper."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "calendar_operations", ROOT / "scripts/calendar-development.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if __name__ == "__main__":
    module.preflight()
    result = module.compose(
        "exec",
        "-T",
        "project-work",
        "python",
        "-c",
        (ROOT / "tests/working_calendar/postgres_check.py").read_text(encoding="utf-8"),
        capture=True,
    )
    if result.returncode:
        print(
            "Calendar PostgreSQL or cleanup verification failed; private diagnostics omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Calendar PostgreSQL schema, publication race, replay and owned cleanup verified.")

    projects = module.compose(
        "exec",
        "-T",
        "project-work",
        "python",
        "-c",
        (ROOT / "tests/projects/postgres_check.py").read_text(encoding="utf-8"),
        capture=True,
    )
    if projects.returncode:
        print(
            "Project PostgreSQL race or cleanup verification failed; private diagnostics omitted.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Project schema, commitment/publication races, replay and owned cleanup verified.")
