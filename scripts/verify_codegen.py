#!/usr/bin/env python3
"""Non-mutating GraphQL schema and frontend codegen verification.

Generates the Gateway GraphQL schema and frontend TypeScript client types into a
temporary location, then verifies that working-tree files match without overwriting
tracked or unstaged changes.
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_python_exe() -> str:
    venv_win = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    venv_nix = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_win.is_file():
        return str(venv_win)
    if venv_nix.is_file():
        return str(venv_nix)
    return sys.executable


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def verify_gateway_schema(temp_dir: Path) -> tuple[bool, str]:
    schema_path = REPO_ROOT / "gateway" / "schema.graphql"
    if not schema_path.is_file():
        return False, f"Gateway schema file missing: {schema_path}"

    current_schema = normalize_newlines(schema_path.read_text(encoding="utf-8"))

    # Generate gateway schema in memory using Python
    export_script = (
        "import sys; "
        "sys.path.insert(0, 'gateway'); "
        "from app.schema import schema; "
        "sys.stdout.buffer.write((schema.as_str() + '\\n').encode('utf-8'))"
    )
    python_exe = get_python_exe()
    result = subprocess.run(
        [python_exe, "-c", export_script],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr_diag = result.stderr.decode("utf-8", errors="replace")
        stdout_diag = result.stdout.decode("utf-8", errors="replace")
        return (
            False,
            f"Failed to export gateway schema (exit code {result.returncode}):\n"
            f"{stderr_diag or stdout_diag or 'No error output'}",
        )

    if not result.stdout:
        return False, "Failed to export gateway schema: generator produced empty output."

    try:
        generated_schema = normalize_newlines(result.stdout.decode("utf-8"))
    except UnicodeDecodeError as err:
        return False, f"Failed to decode generated gateway schema as UTF-8: {err}"

    if current_schema != generated_schema:
        diff = "\n".join(
            difflib.unified_diff(
                current_schema.splitlines(),
                generated_schema.splitlines(),
                fromfile="gateway/schema.graphql (committed/working)",
                tofile="gateway/schema.graphql (generated in memory)",
                lineterm="",
            )
        )
        return False, f"Gateway schema drift detected:\n{diff}"

    return True, "Gateway schema is synchronized."


def verify_frontend_codegen(temp_dir: Path) -> tuple[bool, str]:
    working_generated_dir = REPO_ROOT / "frontend" / "src" / "graphql" / "generated"
    if not working_generated_dir.is_dir():
        return False, f"Frontend generated directory missing: {working_generated_dir}"

    temp_output_dir = temp_dir / "generated"
    temp_output_dir.mkdir(parents=True, exist_ok=True)

    # Use forward slashes in config for cross-platform compatibility
    schema_file = (REPO_ROOT / "gateway" / "schema.graphql").as_posix()
    documents_glob = (REPO_ROOT / "frontend" / "src" / "graphql" / "operations" / "*.graphql").as_posix()
    output_target = f"{temp_output_dir.as_posix()}/"

    temp_config = {
        "schema": schema_file,
        "documents": [documents_glob],
        "generates": {
            output_target: {
                "preset": "@graphql-codegen/client-preset",
                "config": {
                    "useTypeImports": True,
                    "scalars": {
                        "Date": "string",
                        "DateTime": "string",
                        "JSON": "Record<string, unknown>",
                    },
                },
                "presetConfig": {
                    "fragmentMasking": False,
                },
            }
        },
    }

    temp_config_path = temp_dir / "codegen.json"
    temp_config_path.write_text(json.dumps(temp_config, indent=2), encoding="utf-8")

    # Run graphql-codegen with cwd = frontend so npm/node finds the local packages
    cmd = [
        "npx",
        "graphql-codegen",
        "--config",
        str(temp_config_path),
    ]
    is_windows = os.name == "nt"
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT / "frontend",
        shell=is_windows,
        capture_output=True,
    )
    if res.returncode != 0:
        stdout_diag = res.stdout.decode("utf-8", errors="replace")
        stderr_diag = res.stderr.decode("utf-8", errors="replace")
        return (
            False,
            f"graphql-codegen failed in temp directory (exit code {res.returncode}):\n"
            f"STDOUT:\n{stdout_diag}\nSTDERR:\n{stderr_diag}",
        )

    # Compare temp_output_dir against working_generated_dir
    generated_files = {p.relative_to(temp_output_dir): p for p in temp_output_dir.rglob("*") if p.is_file()}
    working_files = {p.relative_to(working_generated_dir): p for p in working_generated_dir.rglob("*") if p.is_file()}

    if not generated_files:
        stdout_diag = res.stdout.decode("utf-8", errors="replace")
        stderr_diag = res.stderr.decode("utf-8", errors="replace")
        return (
            False,
            f"graphql-codegen produced no output files in temp directory.\n"
            f"STDOUT:\n{stdout_diag}\nSTDERR:\n{stderr_diag}",
        )

    if not working_files:
        return False, f"No existing generated files found in working directory: {working_generated_dir}"

    diffs: list[str] = []

    for rel_path, temp_file in generated_files.items():
        if rel_path not in working_files:
            diffs.append(f"Missing file in working directory: {rel_path}")
            continue
        working_file = working_files[rel_path]
        temp_content = normalize_newlines(temp_file.read_text(encoding="utf-8"))
        working_content = normalize_newlines(working_file.read_text(encoding="utf-8"))
        if temp_content != working_content:
            file_diff = "\n".join(
                difflib.unified_diff(
                    working_content.splitlines(),
                    temp_content.splitlines(),
                    fromfile=f"frontend/src/graphql/generated/{rel_path} (working)",
                    tofile=f"frontend/src/graphql/generated/{rel_path} (newly generated)",
                    lineterm="",
                )
            )
            diffs.append(f"Drift in {rel_path}:\n{file_diff}")

    for rel_path in working_files:
        if rel_path not in generated_files:
            diffs.append(f"Orphaned file in working directory (not generated): {rel_path}")

    if diffs:
        return False, "\n\n".join(diffs)

    return True, "Frontend GraphQL client operations are synchronized."


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")

    print("=== Non-Mutating GraphQL Schema & Codegen Verification ===")
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        print("1/2 Verifying Gateway schema consistency...")
        gateway_ok, gateway_msg = verify_gateway_schema(temp_dir)
        if not gateway_ok:
            print(f"FAILED: {gateway_msg}", file=sys.stderr)
            return 1
        print(f"  OK: {gateway_msg}")

        print("2/2 Verifying Frontend codegen consistency (dry-run into temp dir)...")
        frontend_ok, frontend_msg = verify_frontend_codegen(temp_dir)
        if not frontend_ok:
            print(f"FAILED: {frontend_msg}", file=sys.stderr)
            return 1
        print(f"  OK: {frontend_msg}")

    print("\nSUCCESS: GraphQL schema and generated TypeScript operations are in complete synchronization!")
    print("Working tree was preserved without any mutations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
