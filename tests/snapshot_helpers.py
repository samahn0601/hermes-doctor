"""Stdlib-only snapshot helpers for hermes-doctor fixture tests.

The intent is to freeze the public summary contract before adding new
analyzers in v0.2. Snapshots are normalized line-by-line so that volatile
fields (timestamps, host paths) cannot break the test.
"""
from __future__ import annotations

import difflib
import os
import re
import shutil
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def materialize_fixture(case: str, dst_root: Path) -> Path:
    """Copy fixtures/<case>/home into dst_root/.hermes and inflate marker files."""
    src = FIXTURE_ROOT / case / "home"
    home = dst_root / ".hermes"
    shutil.copytree(src, home)
    for marker in list(home.rglob("*.inflate")):
        target = marker.with_suffix("")
        try:
            size_kb = int(marker.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            size_kb = 0
        target.write_text("x" * (size_kb * 1024), encoding="utf-8")
        marker.unlink()
    return home


def read_cron_text(case: str) -> str:
    cron_path = FIXTURE_ROOT / case / "cron.txt"
    return cron_path.read_text(encoding="utf-8") if cron_path.exists() else ""


_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)?")


def normalize(text: str) -> str:
    """Make snapshot output stable across machines and runs."""
    out = _TIMESTAMP_RE.sub("<TIMESTAMP>", text)
    out = re.sub(r"<HERMES_HOME>[^\s\"\)]*", "<HERMES_HOME>", out)
    out = re.sub(r"<HOME>[^\s\"\)]*", "<HOME>", out)
    out = re.sub(r"/private/var/folders/[^\s\"\)]*", "<TMP>", out)
    out = re.sub(r"/tmp/[^\s\"\)]*", "<TMP>", out)
    return out.rstrip() + "\n"


def assert_snapshot(actual: str, snapshot_path: Path) -> None:
    """Compare normalized actual against snapshot file. Refresh on demand."""
    actual = normalize(actual)
    if os.environ.get("HERMES_DOCTOR_SNAPSHOT_UPDATE") == "1":
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(actual, encoding="utf-8")
        return
    if not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(actual, encoding="utf-8")
        raise AssertionError(
            f"Snapshot did not exist; wrote initial value to {snapshot_path}. "
            "Review and re-run."
        )
    expected = snapshot_path.read_text(encoding="utf-8")
    if actual == expected:
        return
    diff = "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=str(snapshot_path),
            tofile="actual",
            lineterm="",
        )
    )
    raise AssertionError(
        "Snapshot mismatch.\n"
        "Re-run with HERMES_DOCTOR_SNAPSHOT_UPDATE=1 to refresh after review.\n\n"
        + diff
    )
