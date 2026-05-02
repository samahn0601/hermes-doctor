from pathlib import Path
import tomllib

import pytest

import hermes_doctor
from hermes_doctor import cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_pyproject():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert hermes_doctor.__version__ == pyproject["project"]["version"]


def test_version_flag_prints_package_version_without_scanning(capsys, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("--version must not build a scan")

    monkeypatch.setattr(cli, "build_scan", explode)

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"hermes-doctor {hermes_doctor.__version__}"


def test_self_check_reports_cli_runtime_and_metadata(capsys, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("--self-check must not build a scan")

    monkeypatch.setattr(cli, "build_scan", explode)
    monkeypatch.setattr(cli, "installed_metadata_version", lambda: hermes_doctor.__version__)

    assert cli.main(["--self-check"]) == 0
    out = capsys.readouterr().out
    assert "Hermes Doctor self-check" in out
    assert f"package_version: {hermes_doctor.__version__}" in out
    assert f"metadata_version: {hermes_doctor.__version__}" in out
    assert "version_consistent: true" in out
    assert "module_file:" in out


def test_self_check_surfaces_metadata_mismatch(capsys, monkeypatch):
    monkeypatch.setattr(cli, "installed_metadata_version", lambda: "0.1.0")

    assert cli.main(["--self-check"]) == 1
    out = capsys.readouterr().out
    assert f"package_version: {hermes_doctor.__version__}" in out
    assert "metadata_version: 0.1.0" in out
    assert "version_consistent: false" in out
    assert "suggestion: reinstall or upgrade hermes-doctor in the active environment" in out
