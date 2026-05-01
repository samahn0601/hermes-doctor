# Changelog

All notable changes to Hermes Doctor will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.1] - 2026-05-01

### Fixed
- **Severity-label mismatch**: a Hermes home with multiple `critical` findings could still be labelled `healthy` (e.g. 5 criticals → 87/100 healthy). The top-line label and severity counts now cannot disagree:
  - `critical >= 1` blocks the `healthy` label.
  - `critical >= 3` forces `unhealthy`.
  - `warning >= 5` blocks the `healthy` label.
- Per-finding penalties strengthened (`warning` 2 → 5, `critical` 8 → 20) so domain scores reflect severity proportionally.

### Added
- `tests/test_label_invariants.py` — direct invariants on `health_status_label` independent of fixtures.
- README badges (PyPI version, supported Python versions, license, CI status).
- GitHub repo description and topics for discoverability.

## [0.2.0] - 2026-05-01

### Added
- Golden fixture corpus under `tests/fixtures/` covering healthy, warning, and critical Hermes home states.
- Snapshot-based regression tests (`tests/test_snapshots.py`) using stdlib-only normalization. Freezes the public summary contract before adding new analyzers.
- `Non-goals` section in README to make the safety boundary explicit and discourage scope creep.
- PyPI Trusted Publishing release workflow at `.github/workflows/release.yml`. Publishes on tag `v*`.
- First PyPI publication. `pipx install hermes-doctor` and `pipx run hermes-doctor` now work.

### Changed
- README headline reframed as a one-line positioning statement: *Linters check your code. Hermes Doctor checks your agent's mind.*
- README install path now leads with `pipx run hermes-doctor` (zero-install ephemeral execution).
- Roadmap rewritten to reflect the v0.2/v0.3/v1.0 priority order: trust infrastructure first, dry-run suggestions later, deliberately frozen at v1.

## [0.1.0] - 2026-05-01

### Added
- Initial public preview release.
- Read-only health scanner across five domains: `markdown`, `memory_skills`, `reminder_cron`, `session_context`, `runtime_gateway`.
- Heuristic domain scoring with weakest-domain weighting.
- Best-effort redaction for paths, secret-like strings, and identifier-like strings.
- CLI flags: `--summary`, `--json`, `--write-report`, `--fail-on`, `--include`, `--include-project-hub`, `--debug-raw`.
- Markdown and JSON report rendering, plus atomic `latest.md` refresh.
