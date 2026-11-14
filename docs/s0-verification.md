# S0 verification and handoff

Date 14 November 2026.

Status: implementation and local verification completed, pending owner review,
manual Git actions and remote CI. S1 has not started.

## Delivered scope

The prior frontend, six Python application services, scripts, historical
documentation, Compose files and environment template are isolated under legacy.
The new app lives at apps/web and contains only an honest preparation page.
It imports no old shell, portal, authentication or business implementation.

The owner selected separate fresh development data for the replacement while
preserving legacy data. No replacement database, realm, session store, worker,
queue or account was created. No running service was started, stopped,
recreated or rebuilt during S0.

Architecture, service/data ownership, reserved frontend module paths and runtime
pins are recorded in s0-architecture.md. An explicit file-by-file preservation
inventory is available in s0-relocation.json.

## Preservation and recovery

The starting committed baseline was
fc8fc6f632eaca55f8e54ffdcc65b048d0e83592 on portal-r1-baseline.
That branch, commit and Git index remain unchanged.

Recovery material is under:

.local/recovery/s0-20261114T071644Z/

| File | Purpose |
| --- | --- |
| committed-baseline.zip | Complete source at the initial committed baseline |
| working-source.zip | Existing tracked and untracked source before S0 |
| recovery-manifest.json | Per-file hashes, original deletions and recovery metadata |
| unstaged-changes.patch | Original working-tree changes relative to the baseline |

Both archives passed CRC validation. Every working-source archive entry was
compared byte-for-byte by SHA-256 against its source before relocation.
The source snapshot excludes private environment files, Git metadata, ignored
dependencies, virtual environments and build/test output. It contains no matches
for the current local secret values. The private root .env was retained in place
and its unchanged hash was checked.

All 402 initial source files are accounted for. There are 394 relocations,
385 files with unchanged contents, and 17 explicit adaptations. Adaptations
cover CI paths and the new mandatory gate, relocated Compose bind paths, local
verification toolchain lookup, the default report destination, and protection
of the replacement development project from legacy recovery tooling, plus a
targeted formatting correction in one preserved UI test.

Files already deleted in the initial dirty worktree remain deleted in the
preserved experiment at legacy/experiments/portal-web. The 160 accepted baseline
frontend files were separately extracted into legacy/frontend from the verified
committed-source archive. Their hashes and the one report-path adaptation are
recorded in s0-legacy-baseline.json. No Git checkout, restore or reset was used. Relocated generated caches were
preserved locally outside the executable source before a clean build attempt.
The package and lockfile bytes matched before the existing dependency cache was
moved to the accepted frontend. Existing uncommitted portal work is preserved
rather than automatically adopted by the new application.

For source recovery, first extract the archives into a separate directory and
verify hashes against recovery-manifest.json. Review the extracted source and
the original deletion list before restoring selected files. Do not extract over
the current worktree or replace private environment/data without an owner-reviewed
recovery action. Recovery archives are local files, not a new Git commit.

## Verification results

| Check | Actual result |
| --- | --- |
| Complete S0 PowerShell entrypoint | Passed structure checks, formatting, ESLint, TypeScript and production build |
| S0 machine-readable structure suite | 11 passed, zero skips, failures or errors |
| Report guard negative probes | Rejected both zero-test and unexpectedly skipped suites |
| New app production dependency audit | Zero findings |
| New app full install audit | 8 development dependency findings, 7 moderate and 1 high |
| New structure Python Ruff lint/format | Passed |
| Relocated Gateway unit tests | 138 passed |
| Accepted baseline frontend unit tests | 84 passed in all 16 files, zero skips or failures |
| Preserved experimental frontend unit tests, before separation | 104 passed in 18 files |
| Accepted baseline production build | Passed after generated caches were preserved outside its execution path |
| Accepted baseline static verification | Passed Python lint/format, six service type checks, frontend format/lint/typecheck |
| Relocated schema and client generation | Passed again after accepted frontend recovery, without writing source outputs |
| Root and both legacy Compose definitions | Config validation passed |
| PowerShell and Bash script syntax | Passed |
| CI YAML and mandatory gate paths | Parsed and verified all seven required jobs |
| New app production trace boundaries | All 2174 checked file references stayed inside apps/web |
| Pinned Node Docker image manifest | Registry metadata verified |
| File inventory and private environment | Hash verification passed |
| Git index, HEAD and branch | Unchanged |
| Product plan DOCX | Hash unchanged |

The executed new-app command was .\scripts\test-s0.ps1.
It runs scripts/check_structure.py and scripts/run_structure_tests.py, then
the app's format:check, lint, typecheck and build commands.
The new npm graph was installed with npm --prefix apps/web ci --ignore-scripts.
Its production audit used npm --prefix apps/web audit --omit=dev.

The relocated test runs used the existing local Python environment for
legacy/gateway pytest and the existing frontend installation for Vitest with
one worker and native configuration loading. This is a local relocation check,
not proof of freshly installed service-specific CI environments.

The initial offline dependency install failed on a missing cached package.
The pinned install then completed through normal package-registry access.
The accepted legacy frontend initially failed during the CSS compiler subprocess,
including with normal process access. After preserving and removing relocated
generated caches from its execution path, the clean production build passed.
A diagnostic build invoked from the repository root failed because that directory
has no package.json; it was rerun from legacy/frontend.
The first complete S0 wrapper caught a PostCSS formatting issue. After correction,
the whole wrapper passed. The legacy static entrypoint also found one retained
UI test with a formatting mismatch. That file was formatted while preserving
its assertions. Restricted Git Bash could not initialize; the read-only
syntax checks passed with normal process access. None of those failed attempts
is counted as a successful check.

An ad-hoc broader Ruff check of the preserved codegen helper reported existing
style findings outside the legacy CI lint scope. Its functional schema/codegen
verification passed. The six legacy applications retain their existing CI
lint/typecheck rules.

An accepted-frontend unit attempt passed 82 tests across 15 files but had an
unhandled worker-start timeout for publications.test.tsx. That run is not counted
as a pass. The focused authentication test then passed all 10 tests. The whole
suite was rerun without a competing production build, preserving the assertions
and existing timeouts. Initial thread-worker attempts were stopped after stalling;
the separate-process worker mode was used for diagnosis and verification.
The final complete run passed 84 tests in all 16 files, zero pending/skipped
assertions and zero failures. Its success flag and every assertion status were
verified in legacy/test-results/reports/s0-frontend-unit.json. The executed command
from legacy/frontend was:

```powershell
node node_modules/vitest/vitest.mjs run --configLoader native --maxWorkers=1 --pool=forks --reporter=json --outputFile=../test-results/reports/s0-frontend-unit.json
```

Development dependency audit findings remain documented and were not addressed
by an unapproved dependency upgrade. The production audit is not a claim that
the entire development dependency graph is clear.

## Runtime and data preservation evidence

Read-only Docker inspection established the existing project ownership,
service names and volume/bind mounts before source relocation. All 26 original
legacy container IDs were identical afterward, and all 26 were running and
healthy. A separate project named deploy also has six containers; its unhealthy
Kafka process is unrelated to Taskspace and was not changed. Replacement runtime resources numbered zero. Therefore no old/new
message consumers or execution workers were introduced together by S0.

Existing bind mount sources stayed in infrastructure. Legacy Compose definitions
resolve them using ../infrastructure. Existing volume, queue, service, realm and
database identifiers were not renamed.

The running containers retain their original Compose configuration-path labels.
Manage that stack only with the explicitly selected legacy/compose.yaml and
its original project name. S0 did not recreate containers merely to refresh
those metadata labels.

The root compose.yaml belongs to taskspace-portals-development and declares only
the new web scaffold, with port 3020. Port 3010 continues to belong to the
existing legacy frontend. It is not a preview or acceptance result for the new app.

## Checks not performed

No Docker image was built and no replacement server was launched in S0.
No migrations, PostgreSQL integration suites, account provisioning, credential
reset, browser sign-in, service outage/recovery or deployment was performed.
Those actions need the stage-specific scope and runtime authorization.

Remote GitHub Actions was not run or claimed. All six historical gates were
retained and rebased to legacy, and the S0 job is additionally required.
The experimental portal redirect conflicted with historical browser expectations.
Legacy CI now uses the separately recovered accepted frontend baseline, preserving
that experiment without substituting it for accepted behavior. Browser execution
against the unchanged running experimental image would not verify this recovered
source. Fresh isolated-stack execution remains a remote CI/manual review gap.
Replacement behavior coverage is introduced with the corresponding new stages.

## Owner review and manual Git steps

Review the file inventory and source classification first. Confirm the data
decision, the people/identity ownership choice and the reserved module paths.
Choose the target branch manually; the existing dirty branch was not switched.

Useful read-only PowerShell commands are:

```powershell
git status --short
git diff --stat
git diff -- .github/workflows/ci.yml compose.yaml .nvmrc README.md
Get-Content docs/s0-architecture.md
Get-Content docs/s0-relocation.json
.\scripts\test-s0.ps1
```

After inspecting all new files and confirming the target branch, the owner can
stage the explicitly reviewed scope, including the old tracked path removals:

```powershell
git add -A -- frontend gateway services scripts docs apps legacy tests infrastructure README.md compose.yaml compose.test.yaml .env.example .nvmrc .github/workflows/ci.yml
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "refactor: establish S0 portal structure and isolate legacy"
```

These commands are manual instructions only. Push, PR creation, merge and
post-merge verification remain owner actions. S1 requires subsequent explicit
authorization after the S0 review.
