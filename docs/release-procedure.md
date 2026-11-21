# Release procedure

This is the step-by-step procedure behind [release-checklist.md](release-checklist.md).
ForgeKit is pre-1.0; every release is explicitly labelled.

## 1. Decide the release level

| Level | Requirements |
|-------|--------------|
| Alpha (`0.x`) | Linux validated, tests/lint/packaging green, limitations documented. macOS/Windows not claimed. |
| Beta | Above, plus external testing on at least two distributions and an independent review of backup/restore. |
| 1.0 | Stable CLI and configuration schema, validated platforms, documented security review. |

Current status and reasoning: see [the audit](audit-2026-11-post-pr2.md).

## 2. Prepare the tree

```bash
git checkout main && git pull
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

1. Bump `__version__` in `src/forgekit/__init__.py` (single source of truth).
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under the new version with the
   date.
3. Update `docs/release-checklist.md` with what was actually verified. Do not tick
   anything you did not run.
4. Re-read `SECURITY.md`, `docs/platform-support.md` and
   `docs/backup-safety.md` for stale claims.

## 3. Verify locally

```bash
ruff check src/ tests/
ruff format --check src/ tests/
pytest -q --cov=forgekit --cov-report=term-missing
python -m build
```

Install both artifacts in clean environments outside the repository:

```bash
python -m venv /tmp/wheel && /tmp/wheel/bin/pip install dist/*.whl
/tmp/wheel/bin/pip check && /tmp/wheel/bin/forge doctor && /tmp/wheel/bin/forge --version

python -m venv /tmp/sdist && /tmp/sdist/bin/pip install dist/*.tar.gz
/tmp/sdist/bin/pip check && /tmp/sdist/bin/forge system memory --json | python -m json.tool
```

Exercise the backup round trip, including verify and restore into a temporary
directory.

## 4. Verify CI

- Linux job green on Python 3.11, 3.12 and 3.13 (lint, format, coverage gate,
  wheel smoke test, sdist smoke test, backup round trip).
- `Platforms (experimental)` results recorded; they do not block the release and
  do not imply support.

## 5. Publish

```bash
git tag -a v0.2.0 -m "ForgeKit 0.2.0"
git push origin v0.2.0
# build from a clean checkout of the tag, then:
python -m twine upload dist/forgekit-0.2.0*
```

Use a PyPI token stored outside the repository. After publishing:

1. Install the released version in a fresh environment and run `forge doctor`.
2. Create the GitHub release from the tag using the changelog section.
3. Confirm private vulnerability reporting is enabled.
4. Announce the release level honestly (alpha) and link the limitations.

## 6. If something is wrong

- Wheel/sdist problem: yank the release on PyPI and publish a patch.
- Safety regression in backup/restore: publish a security note, keep the affected
  version documented in `SECURITY.md`, and reproduce the issue in a regression
  test before fixing it.
