"""Regression checks for source isolation and fail-closed CI path handling."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("structure", ROOT / "scripts/check_structure.py")
assert spec and spec.loader
structure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(structure)


class RepositoryStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="taskspace-structure-")
        self.addCleanup(self.directory.cleanup)
        self.fixture = Path(self.directory.name)
        for name in structure.REQUIRED_FILES:
            destination = self.fixture / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)

    def test_membership_acceptance_cannot_be_omitted(self) -> None:
        runner = self.fixture / "scripts/run-s1-acceptance.py"
        runner.write_text(
            runner.read_text(encoding="utf-8").replace(
                'specs.append("tests/e2e/project-membership.spec.ts")', "pass"
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any("S8 membership browser" in e for e in structure.check_repository(self.fixture))
        )

    def test_membership_runtime_cannot_be_omitted(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text(encoding="utf-8").replace(
                "python scripts/membership-development.py up --apply-migration", "echo omitted"
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                "S8 membership source/runtime" in e
                for e in structure.check_repository(self.fixture)
            )
        )

    def test_project_acceptance_cannot_be_omitted(self) -> None:
        runner = self.fixture / "scripts/run-s1-acceptance.py"
        runner.write_text(
            runner.read_text(encoding="utf-8").replace(
                'specs.append("tests/e2e/manager-projects.spec.ts")', "pass"
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any("S7 project browser" in e for e in structure.check_repository(self.fixture))
        )

    def test_calendar_acceptance_cannot_be_omitted(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text(encoding="utf-8").replace(
                "python scripts/calendar-development.py up --apply-migration", "echo omitted"
            ),
            encoding="utf-8",
        )
        self.assertTrue(any("S6 calendar" in e for e in structure.check_repository(self.fixture)))

    def test_missing_authentication_ci_gate_is_rejected(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text().replace("needs.s1-authentication.result", "needs.omitted.result")
        )
        self.assertTrue(
            any("S1 authentication CI gate" in e for e in structure.check_repository(self.fixture))
        )

    def test_missing_account_entry_ci_gate_is_rejected(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text().replace("needs.s2-account-entry.result", "needs.omitted.result")
        )
        self.assertTrue(
            any("S2 account-entry CI gate" in e for e in structure.check_repository(self.fixture))
        )

    def test_initial_administrator_ci_acceptance_cannot_be_removed(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text().replace(
                "python scripts/initial-admin.py --verify --expect-created", "echo omitted"
            )
        )
        self.assertTrue(
            any(
                "S3 initial administrator CI" in e for e in structure.check_repository(self.fixture)
            )
        )

    def test_current_repository_has_valid_boundaries(self) -> None:
        self.assertEqual(structure.check_repository(ROOT), [])

    def test_legacy_import_is_rejected(self) -> None:
        page = self.fixture / "apps/web/src/app/page.tsx"
        page.write_text('import OldShell from "../../../../../legacy/frontend/src/shell";')
        self.assertTrue(
            any("imports legacy" in e for e in structure.check_repository(self.fixture))
        )

    def test_external_relative_import_is_rejected(self) -> None:
        page = self.fixture / "apps/web/src/app/page.tsx"
        page.write_text('import Secret from "../../../../../../outside";')
        self.assertTrue(any("escapes" in e for e in structure.check_repository(self.fixture)))

    def test_legacy_source_cannot_reappear_at_root(self) -> None:
        (self.fixture / "frontend").mkdir()
        self.assertTrue(
            any("outside legacy" in e for e in structure.check_repository(self.fixture))
        )

    def test_new_workers_are_not_silently_added_in_s0(self) -> None:
        compose = self.fixture / "compose.yaml"
        compose.write_text(compose.read_text() + "  worker:\n    image: unused\n")
        self.assertTrue(
            any("only the new web" in e for e in structure.check_repository(self.fixture))
        )

    def test_replacement_cannot_attach_existing_persistent_data(self) -> None:
        compose = self.fixture / "compose.yaml"
        compose.write_text(compose.read_text() + "volumes:\n  old_data:\n")
        self.assertTrue(
            any("persistent data" in e for e in structure.check_repository(self.fixture))
        )

    def test_dependency_ranges_are_rejected(self) -> None:
        package = self.fixture / "apps/web/package.json"
        data = json.loads(package.read_text())
        data["dependencies"]["next"] = "^16.4.3"
        package.write_text(json.dumps(data))
        self.assertTrue(
            any("exactly pinned" in e for e in structure.check_repository(self.fixture))
        )

    def test_missing_cache_paths_are_rejected(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text().replace("legacy/frontend/package-lock.json", "missing/package-lock.json")
        )
        self.assertTrue(any("cache path" in e for e in structure.check_repository(self.fixture)))

    def test_removed_legacy_ci_gate_is_rejected(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(ci.read_text().replace("  schema-and-codegen:", "  removed-schema:"))
        self.assertTrue(
            any("schema-and-codegen" in e for e in structure.check_repository(self.fixture))
        )

    def test_legacy_recovery_tools_reject_both_development_stacks(self) -> None:
        module_spec = importlib.util.spec_from_file_location(
            "legacy_isolation", ROOT / "legacy/scripts/isolated_test_env.py"
        )
        assert module_spec and module_spec.loader
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        for name in ("enterprise-task-platform-phase2", "taskspace-portals-development"):
            with self.assertRaises(ValueError):
                module.validate_project_name(name)
        module.validate_project_name("taskspace-ci-s0-owned-test")

    def test_missing_legacy_source_fails(self) -> None:
        (self.fixture / "legacy/gateway/requirements.lock").unlink()
        self.assertTrue(
            any("Required source" in e for e in structure.check_repository(self.fixture))
        )

    def test_account_management_runtime_cannot_be_omitted(self) -> None:
        ci = self.fixture / ".github/workflows/ci.yml"
        ci.write_text(
            ci.read_text(encoding="utf-8").replace(
                "python scripts/account-management-development.py up --apply-migration", "omitted"
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                "S4 account management runtime" in e
                for e in structure.check_repository(self.fixture)
            )
        )

    def test_real_email_guard_cannot_be_removed(self) -> None:
        runner = self.fixture / "scripts/run-s1-acceptance.py"
        runner.write_text(
            runner.read_text(encoding="utf-8").replace(
                "assert_capture_delivery()", "omitted_guard()"
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any(
                "Gmail-safe browser acceptance" in e
                for e in structure.check_repository(self.fixture)
            )
        )


if __name__ == "__main__":
    unittest.main()
