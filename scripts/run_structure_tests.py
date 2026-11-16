"""Run the S0 suite with a fail-closed machine-readable report."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINIMUM_TESTS = 12


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests/structure"))
    selected = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "suite": "s0-structure",
        "selected": selected,
        "executed": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }
    valid = (
        result.wasSuccessful()
        and report["executed"] >= MINIMUM_TESTS
        and report["selected"] == report["executed"]
        and report["skipped"] == 0
    )
    report["passed"] = valid
    destination = ROOT / "test-results/reports/structure.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not valid:
        print("S0 report rejected: missing tests, skips, failures or errors.", file=sys.stderr)
        return 1
    print(f"S0 report verified: {result.testsRun} tests, zero skips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
