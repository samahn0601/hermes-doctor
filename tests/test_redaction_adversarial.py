"""Adversarial redaction corpus.

Reports leak data on a *best-effort* basis — these tests harden that
basis by asserting that representative real-world secret and identifier
shapes are stripped before any output reaches the user. One privacy
incident kills the project; spend the test budget here.

Do NOT add real credentials. All values below are obviously synthetic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermes_doctor.cli import Redactor


@pytest.fixture
def redactor(tmp_path: Path) -> Redactor:
    home = tmp_path / "home"
    hermes_home = home / ".hermes"
    return Redactor(home=home, hermes_home=hermes_home)


# ---------- API keys / tokens ----------


@pytest.mark.parametrize(
    "needle",
    [
        "sk-" + "A" * 32,                              # OpenAI-shape
        "nvapi-" + "B" * 40,                           # NVIDIA-shape
        "AIza" + "C" * 35,                             # Google-shape
        "g" + "hp_" + "D" * 36,                        # GitHub PAT
        "github" + "_pat_11A" + "E" * 30,              # GitHub fine-grained PAT
        "xoxb-" + "1" * 12 + "-" + "F" * 24,           # Slack bot token
        "xoxp-" + "2" * 12 + "-" + "G" * 24,           # Slack user token
        "Bearer " + "H" * 40,                          # Generic Bearer
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.SIG_PORTION_HERE_ABC",  # JWT-shape
        "123456:" + "I" * 35,                          # Telegram bot token
    ],
)
def test_secret_token_shapes_are_redacted(redactor: Redactor, needle: str):
    line = f"some context with token={needle} trailing"
    out = redactor.redact(line)
    assert needle not in out, f"Token leaked: {needle[:8]}... in {out!r}"


@pytest.mark.parametrize(
    "phrase",
    [
        "api_key=plain_value_should_be_redacted",
        "API_KEY: VALUE_should_be_redacted",
        "token=abc12345_should_be_redacted",
        "secret = whatever_should_be_redacted",
        "password: hunter2_should_be_redacted",
    ],
)
def test_keyword_assigned_secrets_are_redacted(redactor: Redactor, phrase: str):
    out = redactor.redact(phrase)
    assert "should_be_redacted" not in out, f"Leaked: {out!r}"


# ---------- Identifiers ----------


def test_email_is_redacted(redactor: Redactor):
    out = redactor.redact("contact: alice@example.com end")
    assert "alice@example.com" not in out


def test_phone_number_is_redacted(redactor: Redactor):
    out = redactor.redact("call +82 10-1234-5678 today")
    assert "1234-5678" not in out


def test_telegram_chat_id_is_redacted(redactor: Redactor):
    out = redactor.redact("home: 330658669\nchannel: -1001234567890")
    assert "330658669" not in out
    assert "1001234567890" not in out


# ---------- Paths ----------


def test_macos_user_home_is_redacted(redactor: Redactor):
    out = redactor.redact("file at /Users/alice/secret/notes.md")
    assert "/Users/alice" not in out


def test_linux_user_home_is_redacted(redactor: Redactor):
    out = redactor.redact("file at /home/alice/secret/notes.md")
    assert "/home/alice" not in out


def test_windows_user_home_is_redacted(redactor: Redactor):
    out = redactor.redact(r"file at C:\Users\Alice\Documents\secret.md")
    assert "Alice" not in out


def test_korean_folder_under_redacted_home(tmp_path: Path):
    fake_home = tmp_path / "ansang2"
    redactor = Redactor(home=fake_home, hermes_home=fake_home / ".hermes")
    out = redactor.redact(f"path: {fake_home}/문서/세라/계정.md")
    assert str(fake_home) not in out


# ---------- Combined / realistic cases ----------


def test_cron_command_with_inline_secret_is_redacted(redactor: Redactor):
    line = (
        "Name: r_0001_demo\n"
        "Command: curl -H 'Authorization: Bearer "
        + "Z" * 40
        + "' https://api.example.com/ping\n"
        "Next run: 2099-01-01T09:00:00+09:00\n"
    )
    out = redactor.redact(line)
    assert "Z" * 40 not in out


def test_redaction_does_not_eat_the_whole_line(redactor: Redactor):
    """Sanity: redaction should mask, not delete useful structure."""
    out = redactor.redact("token=" + "Q" * 40 + " was used at 2099-01-01")
    assert "2099-01-01" in out
    assert "<REDACTED" in out
