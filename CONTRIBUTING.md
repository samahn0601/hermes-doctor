# Contributing to Hermes Doctor

Thanks for considering a contribution. This is a deliberately small,
slow-moving project run by a solo maintainer who optimizes for
*credibility and restraint*, not feature volume. Read [README's Non-goals
section](README.md#non-goals) before proposing new functionality.

## Before opening an issue or PR

1. **Read [SECURITY.md](SECURITY.md) first** if you want to paste a report
   anywhere. Do not paste raw memory files, raw skill files, raw cron
   commands, or absolute home paths. Prefer `--summary` or `--json`
   output, redacted again by hand if anything looks personal.
2. Reference findings by their **stable IDs** (`HD-MD-001`, `HD-MEM-002`,
   etc.). The complete list lives in `FINDING_IDS` inside
   `src/hermes_doctor/cli.py`.
3. Include in any bug report: Hermes Doctor version, OS, Python version,
   the exact command run, and the redacted output.

## Out-of-scope contribution proposals

Do not open PRs for these. They will be politely declined to keep the
project's promise intact.

- A `--fix`, `--auto-repair`, or any mutating mode. The doctor writes
  prescriptions; the patient goes to the pharmacy.
- Cloud telemetry, dashboards, or "anonymous usage stats."
- Support for other agent frameworks (AutoGPT, LangChain, …) until Hermes
  itself is stable.
- Adding a runtime dependency to the core scanner. Stdlib only.
- Generic Markdown linting unrelated to Hermes home hygiene.

## In-scope contributions we welcome

- Anonymized fixture cases under `tests/fixtures/` representing real Hermes
  home rot you have observed (with permission of the home's owner).
- New adversarial redaction tests in `tests/test_redaction_adversarial.py`
  for secret or identifier shapes we miss. Use obviously synthetic values.
- New stable findings, with a fresh `HD-…` ID added to `FINDING_IDS`,
  a confidence rating in `FINDING_CONFIDENCE`, and a fixture demonstrating
  the trigger.
- Hermes CLI schema-drift fixtures (`tests/fixtures/<case>/cron.txt` with
  malformed or older formats).
- Documentation that makes the safety boundary clearer.

## Local dev loop

```bash
git clone https://github.com/samahn0601/hermes-doctor.git
cd hermes-doctor
python -m pip install -e .[dev]

python -m pytest -q                                    # full test suite
python -m ruff check .                                 # lint
HERMES_DOCTOR_SNAPSHOT_UPDATE=1 python -m pytest tests/test_snapshots.py
                                                       # refresh fixture snapshots
                                                       # (review the diff before committing)
```

## Pull request checklist

- [ ] All tests pass (`python -m pytest -q`).
- [ ] Ruff is clean (`python -m ruff check .`).
- [ ] If a new finding code is introduced, it has a stable `HD-…` ID and
      a confidence rating.
- [ ] If output formatting changed, fixture snapshots are reviewed and
      updated intentionally (not auto-committed without reading the diff).
- [ ] No new runtime dependency in `pyproject.toml [project] dependencies`.
- [ ] CHANGELOG.md updated under `## [Unreleased]`.

## On the family-physician metaphor

The metaphor is a product-discipline tool, not decoration. Concretely:

- Diagnose, do not operate.
- Prefer screening over emergency surgery.
- A doctor that lists organ failure must not also write "healthy" on
  the chart — see `tests/test_label_invariants.py`.
- Write prescriptions; let the patient (the user) decide whether to take
  them.

If a proposed change does not fit this stance, it does not fit this
project.
