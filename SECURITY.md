# Security & Privacy Reporting

Hermes Doctor scans local personal AI agent state. Reports may incidentally
contain paths, identifiers, or secret-shaped fragments. This document
explains how to report problems safely and what redaction Hermes Doctor
does *not* guarantee.

## TL;DR before opening a public issue

1. **Do not paste raw memory files, raw skill files, raw cron command lines,
   or unredacted Hermes home contents.**
2. Prefer the `--summary` or `--json` output. Both pass through best-effort
   redaction.
3. **Never use `--debug-raw` output in a public issue.** That flag exists
   for *local* debugging only; it includes redacted but full Hermes CLI
   output that may leak more than `--summary`.
4. Re-read the report before pasting. If you see anything that looks like
   a key, token, chat id, or absolute path containing personal info,
   replace it with `<redacted>` manually.
5. Include: Hermes Doctor version (`pip show hermes-doctor`), OS, Python
   version, exact command run, and the **redacted** output.

## What Hermes Doctor redacts (best-effort, not a guarantee)

- Common secret shapes: OpenAI / Google / NVIDIA / GitHub PAT / Slack /
  Telegram bot tokens / JWTs / `Bearer …` headers / `api_key=…`,
  `token=…`, `secret=…`, `password=…` assignments.
- Email addresses, phone numbers in common formats.
- Telegram-style chat / channel / thread identifiers.
- Absolute home paths: `/Users/<name>`, `/home/<name>`, `C:\Users\<Name>`,
  the user-provided `--hermes-home`, and the running user's `$HOME`.

The exact patterns live in `src/hermes_doctor/cli.py` (`SECRET_PATTERNS`
and `IDENTIFIER_PATTERNS`). Adversarial regression tests live in
`tests/test_redaction_adversarial.py`.

## What Hermes Doctor does NOT do

- It is not a formal secret scanner. Heuristic redaction misses things.
- It does not rewrite or sanitize source files on disk.
- It does not strip arbitrary PII inside free-form Markdown content.
- It does not promise zero false-positives or zero false-negatives.

## Reporting a sensitive issue privately

If you believe Hermes Doctor leaked something it should not have, or you
found a vulnerability, do **not** open a public GitHub issue.

Instead, open a [GitHub security advisory](https://github.com/samahn0601/hermes-doctor/security/advisories/new)
with a redacted reproduction. The maintainer will respond when reasonably
possible — this is a solo, low-maintenance project, so please set
expectations accordingly.

## Threat model

Hermes Doctor's threat model is narrow and explicit:

| In scope | Out of scope |
|---|---|
| Accidental leakage of secret-/path-/identifier-shaped strings into reports | Active exfiltration by a malicious user running the tool against someone else's home |
| False reassurance from a "healthy" label that contradicts severity counts | Defending the host machine against arbitrary local code |
| Stale heuristics drifting against Hermes CLI schema changes | Auditing the upstream Hermes Agent itself |

If you are running Hermes Doctor against an account you do not own, that
is not a use case we support or can secure.
