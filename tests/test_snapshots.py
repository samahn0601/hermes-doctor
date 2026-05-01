"""Golden-fixture snapshot tests freezing the v0.1 public summary contract.

These tests document behavior; they are intentionally strict so that any
analyzer change that affects user-visible output forces a snapshot review.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermes_doctor.cli import (
    Redactor,
    build_scan,
    exit_code_for,
    render_summary,
    severity_counts,
)

from snapshot_helpers import (
    FIXTURE_ROOT,
    assert_snapshot,
    materialize_fixture,
    read_cron_text,
)

CASES = ["healthy", "warning", "critical"]


def _scan_for(case: str, tmp_path: Path, monkeypatch):
    home = materialize_fixture(case, tmp_path)
    cron = read_cron_text(case)

    def fake_run_cmd(args, timeout=20):
        if args[:3] == ["hermes", "cron", "list"]:
            return 0, cron
        if args[:2] == ["hermes", "--version"]:
            return 0, "hermes 0.0.0-fixture\n"
        return 0, ""

    monkeypatch.setattr("hermes_doctor.cli.run_cmd", fake_run_cmd)
    redactor = Redactor(home=tmp_path, hermes_home=home)
    scan = build_scan(home)
    return home, redactor, scan


@pytest.mark.parametrize("case", CASES)
def test_summary_snapshot(case, tmp_path, monkeypatch):
    home, redactor, scan = _scan_for(case, tmp_path, monkeypatch)
    summary = render_summary(scan, redactor)
    assert_snapshot(summary, FIXTURE_ROOT / case / "expected_summary.txt")


def test_healthy_has_no_actionable_findings(tmp_path, monkeypatch):
    _, _, scan = _scan_for("healthy", tmp_path, monkeypatch)
    counts = severity_counts(scan["findings"])
    assert counts["critical"] == 0, scan["findings"]
    assert counts["warning"] == 0, scan["findings"]
    assert exit_code_for(scan, "critical") == 0
    assert exit_code_for(scan, "warning") == 0


def test_warning_triggers_warning_only(tmp_path, monkeypatch):
    _, _, scan = _scan_for("warning", tmp_path, monkeypatch)
    counts = severity_counts(scan["findings"])
    assert counts["critical"] == 0, scan["findings"]
    assert counts["warning"] >= 1, scan["findings"]
    assert exit_code_for(scan, "critical") == 0
    assert exit_code_for(scan, "warning") == 2


def test_critical_triggers_critical_and_fail_on_critical(tmp_path, monkeypatch):
    _, _, scan = _scan_for("critical", tmp_path, monkeypatch)
    counts = severity_counts(scan["findings"])
    assert counts["critical"] >= 1, scan["findings"]
    assert exit_code_for(scan, "critical") == 2
    assert exit_code_for(scan, "warning") == 2


def test_score_monotonic_across_cases(tmp_path, monkeypatch):
    """healthy >= warning >= critical for the overall score."""
    scores = []
    for case in CASES:
        home = materialize_fixture(case, tmp_path / case)
        cron = read_cron_text(case)
        monkeypatch.setattr(
            "hermes_doctor.cli.run_cmd",
            lambda args, timeout=20, _c=cron: (0, _c if args[:3] == ["hermes", "cron", "list"] else ""),
        )
        scan = build_scan(home)
        scores.append(scan["scores"]["overall"])
    assert scores[0] >= scores[1] >= scores[2], scores
