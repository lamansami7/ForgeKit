# Release checklist

ForgeKit is pre-1.0. This is a checklist, not a claim of release readiness.

- [ ] Review all outstanding bugs, safety regressions, dependencies and documentation.
- [ ] Run `ruff check src/ tests/`, `ruff format --check src/ tests/` and `pytest --cov=forgekit --cov-report=term-missing` without network or root.
- [ ] Run CI on Linux with Python 3.11, 3.12 and 3.13; investigate every failure.
- [ ] Build both distributions with `python -m build`; install the wheel and sdist in separate clean virtual environments outside the source tree; run `pip check`, `forge --help`, `forge --version`, `forge doctor` and representative JSON commands.
- [ ] Exercise backup create/verify/restore, including corrupt and malicious archives and recovery on representative filesystems. Keep an independent copy of important data.
- [ ] Review backup code and other data-writing operations independently; document any unresolved security findings. Restore is not transactional and does not preserve all metadata.
- [ ] Test platform-specific behavior on actual supported distributions; macOS/Windows remain experimental until independently tested and documented.
- [ ] Verify the changelog, version, documentation, license, issue templates and private security contact. Review outputs for sensitive data.
- [ ] Decide whether unresolved limitations are acceptable for the specific release. Do not call it 1.0 or publish it until maintainers explicitly approve.
