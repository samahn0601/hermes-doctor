# Hermes Doctor Health Report

## Overall
- generated_at: 2099-01-01T09:00:00+09:00
- score: 86 / 100
- status: healthy
- findings: 3

## Domain Scores
- markdown: 100
- memory_skills: 98
- reminder_cron: 92
- session_context: 100
- runtime_gateway: 100

## Top Findings
1. [CRITICAL] Active reminder missing cron job (reminder.cron_missing)
   - evidence: r_0007
   - suggestion: Do not auto-repair; compare SSoT first.
2. [WARNING] Memory/skill size warning (memory.size)
   - evidence: <HERMES_HOME>/memories/notes.md size=84KB
   - suggestion: Check load frequency.
3. [INFO] Large reference file (md.size)
   - evidence: <HERMES_HOME>/skills/example/reference.md size=240KB
   - suggestion: Reference files are loaded on demand; confirm it is not always injected.

## Scanner Summary
- markdown: `{"files_scanned": 42, "total_bytes": 512000, "total_lines": 9000}`
- memory_skills: `{"files_scanned": 18}`
- reminder_cron: `{"reminder_ids": ["r_0001", "r_0007"], "cron_ids": ["r_0001"]}`
- session_context: `{"session_files": 12}`
- runtime_gateway: `{"recent_error_events": 0, "recent_warning_events": 0}`

## Safety Notes
- Example uses synthetic data only.
- Hermes Doctor v1 is observational and read-only.
- Review real reports before sharing them publicly.
