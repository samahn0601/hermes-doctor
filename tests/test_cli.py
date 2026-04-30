from pathlib import Path
import json

from hermes_doctor.cli import (
    Redactor,
    ReminderCronChecker,
    build_scan,
    exit_code_for,
    public_scan,
    render_summary,
    write_report_files,
)


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / ".hermes"
    (home / "memories").mkdir(parents=True)
    (home / "skills").mkdir()
    (home / "sessions").mkdir()
    (home / "logs").mkdir()
    (home / "memories" / "REMINDERS.md").write_text("## Active\n- [ ] 2099-01-01 09:00 KST | project=test | hello | id=r_0001\n", encoding="utf-8")
    return home


def test_redactor_masks_paths_tokens_and_identifiers(tmp_path):
    redactor = Redactor(home=tmp_path, hermes_home=tmp_path / ".hermes")
    chat_id = str(330000000 + 658669)
    fake_bot_token = str(123456) + ":" + ("a" * 26)
    text = f"{tmp_path}/.hermes token=abc12345 chat_id={chat_id} bot={fake_bot_token} email=a@example.com"
    out = redactor.redact(text)
    assert str(tmp_path) not in out
    assert chat_id not in out
    assert fake_bot_token not in out
    assert "a@example.com" not in out
    assert "<REDACTED_ID>" in out


def test_public_json_excludes_internal_cron_text(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    private_id = str(330000000 + 658669)
    monkeypatch.setattr("hermes_doctor.cli.run_cmd", lambda args, timeout=20: (0, "Name: r_0001_test\nNext run: 2099-01-01T09:00:00+09:00\n" if args[-1] == "list" else f"Telegram configured (home: {private_id})"))
    scan = build_scan(home)
    safe = public_scan(scan)
    dumped = json.dumps(safe)
    assert "cron_text_for_internal_use" not in dumped
    assert private_id not in Redactor(tmp_path, home).redact(dumped)
    assert "raw_outputs" not in dumped


def test_reminder_cron_match_is_healthy(tmp_path):
    home = make_home(tmp_path)
    cron = "Name: r_0001_test\nNext run: 2099-01-01T09:00:00+09:00\n"
    result = ReminderCronChecker(home / "memories" / "REMINDERS.md", cron, Redactor(tmp_path, home)).scan()
    assert result["reminder_ids"] == ["r_0001"]
    assert result["cron_ids"] == ["r_0001"]
    assert result["findings"] == []


def test_reminder_cron_mismatch_is_critical(tmp_path):
    home = make_home(tmp_path)
    cron = "Name: r_0001_test\nNext run: 2099-01-01T10:00:00+09:00\n"
    result = ReminderCronChecker(home / "memories" / "REMINDERS.md", cron, Redactor(tmp_path, home)).scan()
    assert any(f["severity"] == "critical" and f["code"] == "reminder.cron_time_mismatch" for f in result["findings"])


def test_summary_and_fail_on(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    monkeypatch.setattr("hermes_doctor.cli.run_cmd", lambda args, timeout=20: (127, "command not found: hermes"))
    scan = build_scan(home)
    summary = render_summary(scan, Redactor(tmp_path, home))
    assert "Hermes Health:" in summary
    assert exit_code_for(scan, "never") == 0
    assert exit_code_for(scan, "critical") in {0, 2}


def test_atomic_report_latest(tmp_path):
    home = make_home(tmp_path)
    out = write_report_files(home, "# report\n")
    latest = out.with_name("latest.md")
    assert out.exists()
    assert latest.exists()
    assert latest.read_text(encoding="utf-8") == "# report\n"
    assert not list(out.parent.glob("*.tmp"))
