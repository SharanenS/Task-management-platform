#!/usr/bin/env python3
"""Exercise the machine-readable report validator against synthetic fixtures.

Tests that verify_test_reports.py correctly enforces:
1. Passing reports (exit code 0).
2. Missing reports (exit code 1, mandatory report missing error).
3. Zero-test reports (exit code 1, selected ZERO tests error).
4. Skipped tests (exit code 1, unexpected skipped tests error).
5. Failing tests (exit code 1, test failure error).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "verify_test_reports.py"


def run_validator(*args: str) -> tuple[int, str]:
    res = subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
    )
    return res.returncode, res.stdout + res.stderr


def make_junit_xml(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuite name="test" tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">\n'
        f'</testsuite>'
    )


def test_junit_fixtures() -> None:
    print("=== Testing JUnit XML Report Validator Fixtures ===")

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)

        # 1. Test missing report
        code, out = run_validator("--unit-dir", str(temp_dir))
        assert code == 1, f"Expected failure on missing reports, got {code}"
        assert "Mandatory report missing" in out
        print("  [PASS] Missing report correctly failed closed.")

        # 2. Test zero-test report
        for fname in ["pytest-gateway.xml", "pytest-employee.xml", "pytest-work.xml", "pytest-job.xml", "pytest-workflow.xml", "pytest-notification.xml", "vitest.xml"]:
            (temp_dir / fname).write_text(make_junit_xml(tests=0), encoding="utf-8")
        code, out = run_validator("--unit-dir", str(temp_dir))
        assert code == 1, f"Expected failure on zero-test reports, got {code}"
        assert "selected ZERO tests" in out
        print("  [PASS] Zero-test report correctly failed closed.")

        # 3. Test skipped test report
        (temp_dir / "pytest-gateway.xml").write_text(make_junit_xml(tests=15, skipped=1), encoding="utf-8")
        code, out = run_validator("--unit-dir", str(temp_dir))
        assert code == 1, f"Expected failure on skipped tests, got {code}"
        assert "unexpected skipped tests" in out
        print("  [PASS] Unexpected skipped test correctly failed closed.")

        # 4. Test failing test report
        (temp_dir / "pytest-gateway.xml").write_text(make_junit_xml(tests=15, failures=1), encoding="utf-8")
        code, out = run_validator("--unit-dir", str(temp_dir))
        assert code == 1, f"Expected failure on test failures, got {code}"
        assert "recorded 1 test failures" in out
        print("  [PASS] Test failure correctly failed closed.")

        # 5. Test passing reports
        counts = {
            "pytest-gateway.xml": 138,
            "pytest-employee.xml": 40,
            "pytest-work.xml": 61,
            "pytest-job.xml": 69,
            "pytest-workflow.xml": 10,
            "pytest-notification.xml": 23,
            "vitest.xml": 75,
        }
        for fname, count in counts.items():
            (temp_dir / fname).write_text(make_junit_xml(tests=count), encoding="utf-8")
        code, out = run_validator("--unit-dir", str(temp_dir))
        assert code == 0, f"Expected success on valid reports, got {code}: {out}"
        assert "SUCCESS" in out
        print("  [PASS] Passing reports correctly validated.")


def test_playwright_fixtures() -> None:
    print("\n=== Testing Playwright JSON Report Validator Fixtures ===")

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        report_file = temp_dir / "report.json"

        # 1. Missing file
        code, out = run_validator("--playwright-file", str(temp_dir / "missing.json"))
        assert code == 1
        assert "does not exist" in out
        print("  [PASS] Missing Playwright report correctly failed closed.")

        # 2. Zero tests
        report_file.write_text(json.dumps({"stats": {"expected": 0, "unexpected": 0, "flaky": 0, "skipped": 0}}))
        code, out = run_validator("--playwright-file", str(report_file))
        assert code == 1
        assert "selected ZERO tests" in out
        print("  [PASS] Zero-test Playwright report correctly failed closed.")

        # 3. Skipped test
        report_file.write_text(json.dumps({"stats": {"expected": 3, "unexpected": 0, "flaky": 0, "skipped": 1}}))
        code, out = run_validator("--playwright-file", str(report_file))
        assert code == 1
        assert "unexpected skipped tests" in out
        print("  [PASS] Skipped Playwright test correctly failed closed.")

        # 4. Failed test
        report_file.write_text(json.dumps({"stats": {"expected": 2, "unexpected": 1, "flaky": 0, "skipped": 0}}))
        code, out = run_validator("--playwright-file", str(report_file))
        assert code == 1
        assert "unexpected test failures" in out
        print("  [PASS] Failed Playwright test correctly failed closed.")

        # 5. Passing report
        report_file.write_text(json.dumps({"stats": {"expected": 3, "unexpected": 0, "flaky": 0, "skipped": 0}}))
        code, out = run_validator("--playwright-file", str(report_file), "--playwright-min-tests", "3")
        assert code == 0
        assert "SUCCESS" in out
        print("  [PASS] Passing Playwright report correctly validated.")


def main() -> int:
    test_junit_fixtures()
    test_playwright_fixtures()
    print("\nAll 10 validator fixture assertions PASSED successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
