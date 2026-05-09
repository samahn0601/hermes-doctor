from pathlib import Path

from hermes_doctor.cli import MemorySkillsAnalyzer, Redactor, build_scan


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / ".hermes"
    (home / "memories").mkdir(parents=True)
    (home / "skills").mkdir()
    (home / "sessions").mkdir()
    (home / "logs").mkdir()
    (home / "memories" / "REMINDERS.md").write_text(
        "## Active\n- [ ] 2099-01-01 09:00 KST | project=test | hello | id=r_0001\n",
        encoding="utf-8",
    )
    return home


def test_update_readiness_reports_behind_count_and_dirty_repo(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    repo = home / "hermes-agent"
    (repo / "gateway" / "platforms").mkdir(parents=True)
    (repo / "gateway" / "platforms" / "telegram.py").write_text(
        "def _is_connect_timeout(exc):\n    return 'ConnectTimeout' in repr(exc)\n",
        encoding="utf-8",
    )

    def fake_run_cmd(args, timeout=20):
        if args[:3] == ["hermes", "cron", "list"]:
            return 0, "Name: r_0001_test\nNext run: 2099-01-01T09:00:00+09:00\n"
        if args[:2] == ["hermes", "--version"]:
            return 0, "hermes 0.13.0\n"
        if args[:3] == ["git", "-C", str(repo)]:
            if args[3:] == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n"
            if args[3:] == ["rev-list", "--count", "HEAD..@{u}"]:
                return 0, "89\n"
            if args[3:] == ["status", "--short"]:
                return 0, " M gateway/platforms/telegram.py\n"
        return 0, ""

    monkeypatch.setattr("hermes_doctor.cli.run_cmd", fake_run_cmd)
    scan = build_scan(home)

    codes = {f["code"] for f in scan["findings"]}
    assert "update.behind" in codes
    assert "update.local_changes" in codes
    assert scan["update_readiness"]["behind_count"] == 89
    assert "gateway/platforms/telegram.py" in scan["update_readiness"]["local_changes"]


def test_update_readiness_notes_telegram_timeout_patch_signature(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    repo = home / "hermes-agent"
    (repo / "gateway" / "platforms").mkdir(parents=True)
    (repo / "gateway" / "platforms" / "telegram.py").write_text(
        "import httpx\n\ndef _is_connect_timeout(exc):\n    return isinstance(exc, httpx.ConnectTimeout)\n",
        encoding="utf-8",
    )

    def fake_run_cmd(args, timeout=20):
        if args[:3] == ["hermes", "cron", "list"]:
            return 0, "Name: r_0001_test\nNext run: 2099-01-01T09:00:00+09:00\n"
        if args[:3] == ["git", "-C", str(repo)]:
            if args[3:] == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n"
            if args[3:] == ["rev-list", "--count", "HEAD..@{u}"]:
                return 0, "0\n"
            if args[3:] == ["status", "--short"]:
                return 0, ""
        return 0, ""

    monkeypatch.setattr("hermes_doctor.cli.run_cmd", fake_run_cmd)
    scan = build_scan(home)

    assert scan["update_readiness"]["telegram_timeout_patch"] == "present"
    assert any(f["code"] == "update.telegram_patch_present" and f["severity"] == "info" for f in scan["findings"])


def test_update_readiness_warns_when_locally_modified_telegram_patch_is_unrecognized(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    repo = home / "hermes-agent"
    (repo / "gateway" / "platforms").mkdir(parents=True)
    (repo / "gateway" / "platforms" / "telegram.py").write_text("# local edit without known timeout helper\n", encoding="utf-8")

    def fake_run_cmd(args, timeout=20):
        if args[:3] == ["hermes", "cron", "list"]:
            return 0, "Name: r_0001_test\nNext run: 2099-01-01T09:00:00+09:00\n"
        if args[:3] == ["git", "-C", str(repo)]:
            if args[3:] == ["rev-parse", "--is-inside-work-tree"]:
                return 0, "true\n"
            if args[3:] == ["rev-list", "--count", "HEAD..@{u}"]:
                return 0, "0\n"
            if args[3:] == ["status", "--short"]:
                return 0, " M gateway/platforms/telegram.py\n"
        return 0, ""

    monkeypatch.setattr("hermes_doctor.cli.run_cmd", fake_run_cmd)
    scan = build_scan(home)

    assert scan["update_readiness"]["telegram_timeout_patch"] == "unrecognized_local_edit"
    assert any(f["code"] == "update.telegram_patch_unrecognized" and f["severity"] == "warning" for f in scan["findings"])


def test_update_readiness_flags_utf8_bom_in_core_files(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    (home / "SOUL.md").write_bytes(b"\xef\xbb\xbf# soul\n")
    (home / "profiles" / "default").mkdir(parents=True)
    (home / "profiles" / "default" / "distribution.yaml").write_bytes(b"\xef\xbb\xbfname: default\n")

    monkeypatch.setattr("hermes_doctor.cli.run_cmd", lambda args, timeout=20: (127, "command not found: hermes"))
    scan = build_scan(home)

    assert scan["update_readiness"]["bom_files"]
    assert sum(1 for f in scan["findings"] if f["code"] == "update.bom") == 2


def test_memory_skills_flags_platforms_inside_folded_description(tmp_path):
    home = make_home(tmp_path)
    skill = home / "skills" / "bad" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: bad\ndescription: >\n  A skill.\n  platforms: [linux]\n---\n# Body\n",
        encoding="utf-8",
    )

    result = MemorySkillsAnalyzer(home, Redactor(tmp_path, home)).scan()

    assert any(f["code"] == "memory.skill_platforms_folded" and f["severity"] == "warning" for f in result["findings"])


def test_memory_skills_notes_missing_platforms_frontmatter_as_info(tmp_path):
    home = make_home(tmp_path)
    skill = home / "skills" / "legacy" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: legacy\ndescription: old style\n---\n# Body\n", encoding="utf-8")

    result = MemorySkillsAnalyzer(home, Redactor(tmp_path, home)).scan()

    assert any(f["code"] == "memory.skill_platforms_missing" and f["severity"] == "info" for f in result["findings"])
