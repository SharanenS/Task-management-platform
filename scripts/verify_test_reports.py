#!/usr/bin/env python3
"""Machine-readable test report validator for Taskspace CI/CD.

Enforces fail-closed validation of JUnit XML and Playwright JSON reports:
- Ensures mandatory test suites are present.
- Enforces tests > 0 (rejects suites with zero selected tests).
- Enforces failures == 0 and errors == 0.
- Enforces skipped == 0 on mandatory suites (rejects unexpected test skips).
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimum expected tests per unit suite
UNIT_SUITES = {
    "pytest-gateway.xml": {"suite": "Gateway Unit", "min_tests": 138},
    "pytest-employee.xml": {"suite": "Employee Unit", "min_tests": 40},
    "pytest-work.xml": {"suite": "Work Unit", "min_tests": 61},
    "pytest-job.xml": {"suite": "Job Unit", "min_tests": 69},
    "pytest-workflow.xml": {"suite": "Workflow Unit", "min_tests": 10},
    "pytest-notification.xml": {"suite": "Notification Unit", "min_tests": 23},
    "vitest.xml": {"suite": "Frontend Vitest", "min_tests": 75},
}

POSTGRES_SUITES = {
    "pytest-work.xml": {"suite": "Work PostgreSQL", "min_tests": 13},
    "pytest-job.xml": {"suite": "Job PostgreSQL", "min_tests": 22},
    "pytest-workflow.xml": {"suite": "Workflow PostgreSQL", "min_tests": 3},
    "pytest-notification.xml": {"suite": "Notification PostgreSQL", "min_tests": 5},
}


def parse_junit_xml(path: Path) -> tuple[int, int, int, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required report file: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    if root.tag == "testsuites":
        for suite in root.findall("testsuite"):
            total_tests += int(suite.attrib.get("tests", "0"))
            total_failures += int(suite.attrib.get("failures", "0"))
            total_errors += int(suite.attrib.get("errors", "0"))
            total_skipped += int(suite.attrib.get("skipped", "0"))
    elif root.tag == "testsuite":
        total_tests = int(root.attrib.get("tests", "0"))
        total_failures = int(root.attrib.get("failures", "0"))
        total_errors = int(root.attrib.get("errors", "0"))
        total_skipped = int(root.attrib.get("skipped", "0"))
    else:
        # Check if tests are inside root
        suites = root.findall(".//testsuite")
        if suites:
            for suite in suites:
                total_tests += int(suite.attrib.get("tests", "0"))
                total_failures += int(suite.attrib.get("failures", "0"))
                total_errors += int(suite.attrib.get("errors", "0"))
                total_skipped += int(suite.attrib.get("skipped", "0"))
        else:
            testcases = root.findall(".//testcase")
            total_tests = len(testcases)
            total_failures = len(root.findall(".//failure"))
            total_errors = len(root.findall(".//error"))
            total_skipped = len(root.findall(".//skipped"))

    return total_tests, total_failures, total_errors, total_skipped


def verify_junit_directory(dir_path: Path, suite_definitions: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    print(f"--> Validating JUnit XML test reports in: {dir_path}")

    for filename, spec in suite_definitions.items():
        report_file = dir_path / filename
        suite_name = str(spec["suite"])
        min_tests = int(spec["min_tests"])

        if not report_file.is_file():
            errors.append(f"Mandatory report missing: {report_file.name} ({suite_name})")
            continue

        try:
            tests, failures, errs, skipped = parse_junit_xml(report_file)
        except Exception as e:
            errors.append(f"Malformed JUnit XML in {report_file.name}: {e}")
            continue

        print(f"    {suite_name:<25}: {tests} tests, {failures} failures, {errs} errors, {skipped} skipped")

        if tests == 0:
            errors.append(f"{suite_name} selected ZERO tests (expected at least {min_tests})")
        elif tests < min_tests:
            errors.append(f"{suite_name} ran fewer tests than expected: {tests} < {min_tests}")

        if failures > 0:
            errors.append(f"{suite_name} recorded {failures} test failures")
        if errs > 0:
            errors.append(f"{suite_name} recorded {errs} test execution errors")
        if skipped > 0:
            errors.append(f"{suite_name} recorded {skipped} unexpected skipped tests")

    return errors


def verify_playwright_json(report_file: Path, min_tests: int = 1) -> list[str]:
    errors: list[str] = []
    print(f"--> Validating Playwright JSON report: {report_file}")

    if not report_file.is_file():
        return [f"Playwright report file does not exist: {report_file}"]

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Malformed Playwright JSON report: {e}"]

    stats = data.get("stats", {})
    expected_passes = stats.get("expected", 0)
    unexpected = stats.get("unexpected", 0)
    flaky = stats.get("flaky", 0)
    skipped = stats.get("skipped", 0)
    total = expected_passes + unexpected + flaky + skipped

    print(f"    Playwright Stats: Total={total}, Passed={expected_passes}, Failed={unexpected}, Flaky={flaky}, Skipped={skipped}")

    if total == 0:
        errors.append("Playwright suite selected ZERO tests.")
    elif total < min_tests:
        errors.append(f"Playwright suite ran fewer tests than expected: {total} < {min_tests}")

    if unexpected > 0:
        errors.append(f"Playwright recorded {unexpected} unexpected test failures.")
    if flaky > 0:
        errors.append(f"Playwright recorded {flaky} flaky test executions.")
    if skipped > 0:
        errors.append(f"Playwright recorded {skipped} unexpected skipped tests.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Machine-readable test report verifier")
    parser.add_argument("--unit-dir", type=Path, help="Directory containing unit JUnit XML reports")
    parser.add_argument("--postgres-dir", type=Path, help="Directory containing postgres JUnit XML reports")
    parser.add_argument("--playwright-file", type=Path, help="Path to Playwright report.json")
    parser.add_argument("--playwright-min-tests", type=int, default=1, help="Minimum expected Playwright tests")

    args = parser.parse_args()

    all_errors: list[str] = []

    if args.unit_dir:
        all_errors.extend(verify_junit_directory(args.unit_dir, UNIT_SUITES))

    if args.postgres_dir:
        all_errors.extend(verify_junit_directory(args.postgres_dir, POSTGRES_SUITES))

    if args.playwright_file:
        all_errors.extend(verify_playwright_json(args.playwright_file, args.playwright_min_tests))

    if all_errors:
        print("\n==================================================================", file=sys.stderr)
        print("Test Report Verification FAILED (Fail-Closed Enforcement):", file=sys.stderr)
        print("==================================================================", file=sys.stderr)
        for err in all_errors:
            print(f"  [ERROR] {err}", file=sys.stderr)
        return 1

    print("\nSUCCESS: All mandatory machine-readable test reports verified (0 failures, 0 errors, 0 unexpected skips).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
