"""Severity-label invariants. Top-line label cannot disagree with severity tally."""
from __future__ import annotations

from hermes_doctor.cli import health_status_label


def test_zero_findings_high_score_is_healthy():
    assert health_status_label(100, 0, 0) == "healthy"
    assert health_status_label(90, 0, 0) == "healthy"


def test_one_critical_blocks_healthy_label_even_at_high_score():
    """A doctor listing one critical organ-failure cannot also write 'healthy'."""
    assert health_status_label(95, critical=1, warning=0) == "needs attention"
    assert health_status_label(100, critical=1, warning=0) == "needs attention"


def test_three_or_more_criticals_force_unhealthy():
    assert health_status_label(99, critical=3, warning=0) == "unhealthy"
    assert health_status_label(80, critical=5, warning=0) == "unhealthy"


def test_many_warnings_block_healthy_label():
    assert health_status_label(95, critical=0, warning=5) == "needs attention"
    assert health_status_label(95, critical=0, warning=4) == "healthy"


def test_low_score_alone_downgrades_label():
    assert health_status_label(60, critical=0, warning=0) == "unhealthy"
    assert health_status_label(75, critical=0, warning=0) == "needs attention"
