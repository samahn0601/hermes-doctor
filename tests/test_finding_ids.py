"""Stable finding IDs — coverage and shape invariants.

Stable IDs are part of the public contract: users grep for them, reference
them in issues, and pin them in CI scripts. Renumbering is forbidden;
deprecated codes stay reserved.
"""
from __future__ import annotations

import re
from pathlib import Path

import hermes_doctor.cli as cli
from hermes_doctor.cli import (
    FINDING_CONFIDENCE,
    FINDING_IDS,
    confidence_for,
    stable_id_for,
)

SOURCE = Path(cli.__file__).read_text(encoding="utf-8")
USED_CODES = set(re.findall(r'Finding\([^,]+,\s*"[^"]+",\s*"([^"]+)"', SOURCE))


def test_every_code_emitted_in_cli_has_a_stable_id():
    missing = USED_CODES - FINDING_IDS.keys()
    assert not missing, (
        "Every Finding code must have a stable HD-* ID. "
        f"Missing in FINDING_IDS: {sorted(missing)}"
    )


def test_every_code_has_a_confidence():
    missing = USED_CODES - FINDING_CONFIDENCE.keys()
    assert not missing, (
        "Every Finding code must have a confidence rating. "
        f"Missing in FINDING_CONFIDENCE: {sorted(missing)}"
    )


def test_stable_id_format_is_uppercase_hd_dash_segment():
    for code, fid in FINDING_IDS.items():
        assert re.fullmatch(r"HD-[A-Z]{2,4}-\d{3}", fid), f"{code} → {fid} (bad shape)"


def test_no_duplicate_stable_ids():
    seen = set()
    for code, fid in FINDING_IDS.items():
        assert fid not in seen, f"Duplicate stable id {fid} (code: {code})"
        seen.add(fid)


def test_confidence_values_are_constrained():
    allowed = {"high", "medium", "low"}
    bad = {c: v for c, v in FINDING_CONFIDENCE.items() if v not in allowed}
    assert not bad, f"Unrecognized confidence values: {bad}"


def test_stable_id_for_unknown_returns_sentinel():
    assert stable_id_for("totally.fake.code") == "HD-UNKNOWN"


def test_confidence_for_unknown_defaults_medium():
    assert confidence_for("totally.fake.code") == "medium"


def test_finding_dict_includes_id_and_confidence():
    f = cli.Finding(
        severity="warning",
        domain="markdown",
        code="md.size",
        title="t",
        evidence="e",
        suggestion="s",
    )
    d = f.to_dict()
    assert d["id"] == "HD-MD-001"
    assert d["confidence"] == "high"
