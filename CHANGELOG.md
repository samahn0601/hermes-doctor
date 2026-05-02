# Changelog

All notable changes to Hermes Doctor will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.1] - 2026-05-03

### Added
- `--version` prints the source package version without scanning Hermes state.
- `--self-check` reports the active Python executable, module path, source package version, and installed package metadata version. It exits `1` when the active environment is importing a different version than the installed metadata, making stale editable installs and venv/user-local conflicts visible.

### Changed
- Source package version is now kept in sync with `pyproject.toml` and guarded by `tests/test_version_cli.py`.

## [0.3.0] - 2026-05-01

### Added
- **Stable finding IDs**. Every finding now carries a fixed `HD-…` identifier (`HD-MD-001` through `HD-RT-006`) plus a `confidence` rating (`high`/`medium`/`low`). Safe to grep, pin in CI scripts, and reference in issues. See `FINDING_IDS` and `FINDING_CONFIDENCE` in `src/hermes_doctor/cli.py`. Coverage is enforced by `tests/test_finding_ids.py` — every code emitted by the scanner is required to have a stable ID and a confidence rating.
- **Adversarial redaction corpus** (`tests/test_redaction_adversarial.py`). 32 cases covering OpenAI / Google / NVIDIA / GitHub PAT / Slack / Telegram bot tokens, JWTs, `Bearer …`, generic `key=value` secret assignments, emails, phone numbers (incl. Korean format), Telegram-style chat IDs, macOS / Linux / Windows home paths, and Korean folder names under `$HOME`. One synthetic case per shape; no real credentials.
- **SECURITY.md** with safe-reporting guidance (do not paste raw memory / skills / cron commands; redact paths and identifiers; never share `--debug-raw` output publicly) and an explicit threat model.
- **CONTRIBUTING.md** with explicit out-of-scope items, in-scope contributions we welcome, and a PR checklist.
- **GitHub issue template** (`.github/ISSUE_TEMPLATE/bug_report.md`) leading with a SECURITY.md reminder; private security advisory link in `config.yml`.

### Changed
- Summary output now leads each actionable finding with its stable ID:
  `- [HD-MD-001 warning] Markdown file size warning: <HERMES_HOME> size=65KB`
- Markdown report adds `confidence` per finding:
  `1. [HD-MD-001] [WARNING] Markdown file size warning (confidence=high)`
- Phone-number redaction tightened to a digit-group shape (`\d{2,4}-\d{3,4}-\d{3,4}`-style) so ISO dates like `2099-01-01` are no longer mistakenly redacted.
- Inner identifier-redaction threshold lowered from 6 to 4 consecutive digits so 4-digit phone segments cannot leak through.

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
