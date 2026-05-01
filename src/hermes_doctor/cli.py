#!/usr/bin/env python3
"""Hermes Doctor: read-only health scanner for Hermes Agent deployments."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

DOMAINS = [
    "markdown",
    "memory_skills",
    "reminder_cron",
    "session_context",
    "runtime_gateway",
]
WARN_PENALTY = 5
CRIT_PENALTY = 20

# Stable finding IDs: short, greppable, never renumbered.
# New codes append; deprecated codes stay reserved.
FINDING_IDS: dict[str, str] = {
    "md.size": "HD-MD-001",
    "md.line_count": "HD-MD-002",
    "md.tokens": "HD-MD-003",
    "md.broken_wikilink": "HD-MD-004",
    "md.broken_link": "HD-MD-005",
    "memory.duplicate": "HD-MEM-001",
    "memory.size": "HD-MEM-002",
    "memory.project_fact": "HD-MEM-003",
    "reminder.missing": "HD-RMD-001",
    "reminder.duplicate_id": "HD-RMD-002",
    "reminder.outside_active": "HD-RMD-003",
    "reminder.cron_time_mismatch": "HD-RMD-004",
    "reminder.cron_missing": "HD-RMD-005",
    "reminder.cron_orphan": "HD-RMD-006",
    "session.size": "HD-SES-001",
    "gateway.errors": "HD-RT-001",
    "gateway.warnings": "HD-RT-002",
    "runtime.version": "HD-RT-003",
    "runtime.status": "HD-RT-004",
    "runtime.doctor": "HD-RT-005",
    "runtime.cron": "HD-RT-006",
}

# Confidence reflects how reliably a heuristic maps to a real problem.
# Low-confidence findings should imply a manual review action, not silent fixes.
FINDING_CONFIDENCE: dict[str, str] = {
    "md.size": "high",
    "md.line_count": "high",
    "md.tokens": "medium",
    "md.broken_wikilink": "high",
    "md.broken_link": "high",
    "memory.duplicate": "high",
    "memory.size": "high",
    "memory.project_fact": "low",
    "reminder.missing": "high",
    "reminder.duplicate_id": "high",
    "reminder.outside_active": "medium",
    "reminder.cron_time_mismatch": "high",
    "reminder.cron_missing": "high",
    "reminder.cron_orphan": "high",
    "session.size": "high",
    "gateway.errors": "medium",
    "gateway.warnings": "low",
    "runtime.version": "high",
    "runtime.status": "high",
    "runtime.doctor": "high",
    "runtime.cron": "high",
}


def stable_id_for(code: str) -> str:
    """Return the stable HD-* ID for a finding code, or 'HD-UNKNOWN' if missing.

    A missing entry is a bug, not silent behavior — a regression test guards
    that every code in cli.py is mapped.
    """
    return FINDING_IDS.get(code, "HD-UNKNOWN")


def confidence_for(code: str) -> str:
    return FINDING_CONFIDENCE.get(code, "medium")

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}"),  # Telegram bot token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile("g" + r"hp_[A-Za-z0-9_]{20,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),  # JWT-like
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*[^\s'\"]+"),
]
IDENTIFIER_PATTERNS = [
    re.compile(r"(?i)(telegram|chat|channel|thread|home)[^\n:]{0,30}:\s*-?\d{6,}"),
    re.compile(r"(?i)(chat_id|channel_id|thread_id|user_id)\s*[=:]\s*-?\d{6,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?:\+\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]\d{3,4}[\s\-]\d{3,4}"),
]


@dataclass
class Finding:
    severity: str
    domain: str
    code: str
    title: str
    evidence: str
    suggestion: str

    def to_dict(self) -> dict[str, str]:
        d = asdict(self)
        d["id"] = stable_id_for(self.code)
        d["confidence"] = confidence_for(self.code)
        return d


class Redactor:
    """Best-effort renderer guard. Never treat this as a secret scanner guarantee."""

    def __init__(self, home: str | Path | None = None, hermes_home: str | Path | None = None):
        self.home = str(Path(home or Path.home()).expanduser())
        self.hermes_home = str(Path(hermes_home).expanduser()) if hermes_home else None

    def redact(self, text: Any) -> str:
        out = str(text)
        if self.hermes_home:
            out = out.replace(self.hermes_home, "<HERMES_HOME>")
        if self.home:
            out = out.replace(self.home, "<HOME>")
        out = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", "<USERPROFILE>", out)
        out = re.sub(r"/Users/[^/\s]+", "<USER_HOME>", out)
        out = re.sub(r"/home/[^/\s]+", "<HOME>", out)
        for pat in SECRET_PATTERNS:
            out = pat.sub("<REDACTED_SECRET>", out)
        for pat in IDENTIFIER_PATTERNS:
            out = pat.sub(lambda m: "<REDACTED_IDENTIFIER>" if "@" in m.group(0) else re.sub(r"-?\d{4,}", "<REDACTED_ID>", m.group(0)), out)
        return out


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def safe_read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            with path.open("rb") as f:
                data = f.read(max_bytes)
            return data.decode("utf-8", "ignore")
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # pragma: no cover - defensive guard
        return f"\n<!-- READ_ERROR: {type(e).__name__} -->\n"


def strip_markdown_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`]*`", "", text)


def is_project_fact_candidate(text: str) -> bool:
    progress = re.compile(r"completed|done|phase\s*\d+|완료|진행", re.I)
    projectish = re.compile(r"project|status\.md|decisions\.md|프로젝트", re.I)
    stable_context = re.compile(r"trigger|reference|principle|location|structure|SSoT|preference|rule|트리거|참조|원칙|위치|구조|선호|규칙", re.I)
    for line in text.splitlines():
        if not (progress.search(line) or projectish.search(line)):
            continue
        if re.search(r"progress.*reference|reference.*progress|진행\s*상황.*참조|참조.*진행\s*상황", line, re.I):
            continue
        if progress.search(line) and not stable_context.search(line):
            return True
        if projectish.search(line) and not stable_context.search(line):
            return True
    return False


class MarkdownAnalyzer:
    def __init__(self, roots: Iterable[str | Path], redactor: Redactor):
        self.roots = [Path(r).expanduser() for r in roots]
        self.redactor = redactor

    def _iter_md_files(self) -> list[Path]:
        files: list[Path] = []
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        for root in self.roots:
            if not root.exists():
                continue
            if root.is_file() and root.suffix.lower() == ".md":
                files.append(root)
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
                for name in filenames:
                    if name.lower().endswith(".md"):
                        files.append(Path(dirpath) / name)
        return sorted(set(files))

    def _resolve_wikilink(self, link: str, all_stems: set[str], current_dir: Path) -> bool:
        target = link.split("#", 1)[0].split("|", 1)[0].strip()
        return not target or target in all_stems or (current_dir / f"{target}.md").exists()

    def scan(self) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        files = self._iter_md_files()
        all_stems = {p.stem for p in files}
        total_bytes = 0
        total_lines = 0
        for p in files:
            try:
                size = p.stat().st_size
            except FileNotFoundError:
                continue
            total_bytes += size
            text = safe_read_text(p)
            lines = text.splitlines()
            total_lines += len(lines)
            rel = self.redactor.redact(str(p))
            tokens = estimate_tokens(text)
            is_skill_reference = "/skills/" in str(p)
            sev_large = "info" if is_skill_reference else "critical"
            sev_warn = "info" if is_skill_reference else "warning"
            if size > 200 * 1024:
                findings.append(Finding(sev_large, "markdown", "md.size", "Large Markdown file", f"{rel} size={size//1024}KB", "Split or index the document if it is injected often.").to_dict())
            elif size > 60 * 1024:
                findings.append(Finding(sev_warn, "markdown", "md.size", "Markdown file size warning", f"{rel} size={size//1024}KB", "Review load frequency and role.").to_dict())
            if len(lines) > 2000:
                findings.append(Finding(sev_large, "markdown", "md.line_count", "Markdown line count high", f"{rel} lines={len(lines)}", "Consider heading-based split.").to_dict())
            elif len(lines) > 800:
                findings.append(Finding(sev_warn, "markdown", "md.line_count", "Markdown line count warning", f"{rel} lines={len(lines)}", "Check navigability.").to_dict())
            if tokens > 24000:
                findings.append(Finding(sev_large, "markdown", "md.tokens", "Estimated tokens high", f"{rel} tokens≈{tokens}", "Avoid direct context injection; index instead.").to_dict())
            elif tokens > 8000:
                findings.append(Finding(sev_warn, "markdown", "md.tokens", "Estimated tokens warning", f"{rel} tokens≈{tokens}", "Consider a summary file.").to_dict())
            link_text = strip_markdown_code(text)
            for wikilink in re.findall(r"\[\[([^\]]+)\]\]", link_text):
                if not self._resolve_wikilink(wikilink, all_stems, p.parent):
                    sev = "info" if is_skill_reference else "critical" if p.name.upper() == "INDEX.md" else "warning"
                    findings.append(Finding(sev, "markdown", "md.broken_wikilink", "Broken wikilink", f"{rel} -> [[{wikilink}]]", "Check target note exists.").to_dict())
            for _label, link in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", link_text):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith("#"):
                    continue
                if is_skill_reference and link.startswith("/"):
                    continue
                target = (p.parent / link.split("#", 1)[0]).resolve()
                if link and not target.exists():
                    sev = "info" if is_skill_reference else "warning"
                    findings.append(Finding(sev, "markdown", "md.broken_link", "Broken Markdown link", f"{rel} -> ({link})", "Check relative link target.").to_dict())
        return {"files_scanned": len(files), "total_bytes": total_bytes, "total_lines": total_lines, "findings": findings}


class MemorySkillsAnalyzer:
    def __init__(self, hermes_home: Path, redactor: Redactor):
        self.hermes_home = hermes_home
        self.redactor = redactor

    def scan(self) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        targets: list[Path] = []
        for sub in ["skills", "memories"]:
            root = self.hermes_home / sub
            if root.exists():
                targets.extend(root.rglob("*.md"))
        seen: dict[str, Path] = {}
        for p in sorted(targets):
            if p.name == "REMINDERS.md":
                continue
            text = safe_read_text(p)
            rel = self.redactor.redact(str(p))
            size = p.stat().st_size
            normalized = re.sub(r"\s+", " ", text.strip().lower())
            h = hashlib.sha1(normalized.encode("utf-8", "ignore")).hexdigest() if normalized else ""
            is_skill_reference = "/skills/" in str(p)
            if h and h in seen and not is_skill_reference:
                findings.append(Finding("warning", "memory_skills", "memory.duplicate", "Exact duplicate Markdown candidate", f"{rel} duplicates {self.redactor.redact(str(seen[h]))}", "Review manually; v1 does not merge.").to_dict())
            elif h:
                seen[h] = p
            if size > 200 * 1024:
                sev = "info" if is_skill_reference else "critical"
                findings.append(Finding(sev, "memory_skills", "memory.size", "Memory/skill file too large", f"{rel} size={size//1024}KB", "Consider externalization or split.").to_dict())
            elif size > 60 * 1024:
                sev = "info" if is_skill_reference else "warning"
                findings.append(Finding(sev, "memory_skills", "memory.size", "Memory/skill size warning", f"{rel} size={size//1024}KB", "Check load frequency.").to_dict())
            if "/memories/" in str(p) and not p.name.startswith("project_") and is_project_fact_candidate(text):
                findings.append(Finding("warning", "memory_skills", "memory.project_fact", "Project fact candidate in general memory", rel, "Move mutable project facts to an SSoT file if applicable.").to_dict())
        return {"files_scanned": len(targets), "findings": findings}


class ReminderCronChecker:
    def __init__(self, reminders_path: Path, cron_text: str, redactor: Redactor):
        self.reminders_path = reminders_path
        self.cron_text = cron_text or ""
        self.redactor = redactor

    def _entries(self) -> list[tuple[str, str, str, int, str | None]]:
        if not self.reminders_path.exists():
            return []
        section: str | None = None
        entries = []
        for line_no, line in enumerate(safe_read_text(self.reminders_path).splitlines(), 1):
            if line.startswith("## "):
                section = line.strip()
            m = re.search(r"- \[([^\]]*)\].*?id=(r_\d{4})\b", line)
            if m:
                entries.append((m.group(1).strip(), m.group(2), line, line_no, section))
        return entries

    def _cron_ids(self) -> set[str]:
        return set(re.findall(r"(?<!\w)(r_\d{4})(?!\d)", self.cron_text))

    def _cron_next_runs(self) -> dict[str, str]:
        runs: dict[str, str] = {}
        current: str | None = None
        for line in self.cron_text.splitlines():
            m = re.search(r"Name:\s+.*?(r_\d{4})(?!\d)", line)
            if m:
                current = m.group(1)
                continue
            m = re.search(r"Next run:\s+([^\s]+)", line)
            if m and current:
                runs[current] = m.group(1)
                current = None
        return runs

    def scan(self) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        rel = self.redactor.redact(str(self.reminders_path))
        if not self.reminders_path.exists():
            return {"reminder_ids": [], "cron_ids": sorted(self._cron_ids()), "findings": [Finding("info", "reminder_cron", "reminder.missing", "REMINDERS.md not found", rel, "Create one if you use Hermes reminders.").to_dict()]}
        entries = self._entries()
        active_ids = {rid for status, rid, _line, _line_no, _section in entries if status == ""}
        all_ids = [rid for _status, rid, _line, _line_no, _section in entries]
        cron_ids = self._cron_ids()
        for rid in sorted({rid for rid in all_ids if all_ids.count(rid) > 1}):
            findings.append(Finding("critical", "reminder_cron", "reminder.duplicate_id", "Duplicate reminder id", rid, "Review manually; v1 does not merge.").to_dict())
        for status, rid, _line, line_no, section in entries:
            if status == "" and section and "Active" not in section and "미완료" not in section:
                findings.append(Finding("warning", "reminder_cron", "reminder.outside_active", "Unchecked reminder outside Active section", f"{rid} line={line_no}", "Check reminder SSoT structure.").to_dict())
        cron_next = self._cron_next_runs()
        for status, rid, line, _line_no, _section in entries:
            if status or rid not in cron_next:
                continue
            m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+KST", line)
            if m and not cron_next[rid].startswith(f"{m.group(1)}T{m.group(2)}"):
                findings.append(Finding("critical", "reminder_cron", "reminder.cron_time_mismatch", "Reminder and cron next-run mismatch", f"{rid} ssot={m.group(1)} {m.group(2)} cron_next={cron_next[rid]}", "Confirm intended notification time before changing anything.").to_dict())
        for rid in sorted(active_ids - cron_ids):
            findings.append(Finding("critical", "reminder_cron", "reminder.cron_missing", "Active reminder missing cron job", rid, "Do not auto-repair; compare SSoT first.").to_dict())
        for cid in sorted(cron_ids - active_ids):
            findings.append(Finding("critical", "reminder_cron", "reminder.cron_orphan", "Cron job has no active reminder", cid, "Do not auto-delete; compare SSoT first.").to_dict())
        return {"reminder_ids": sorted(active_ids), "cron_ids": sorted(cron_ids), "findings": findings}


def run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, (cp.stdout or "") + (cp.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {args[0]}"
    except Exception as e:
        return 999, f"{type(e).__name__}: {e}"


class RuntimeAnalyzer:
    def __init__(self, hermes_home: Path, redactor: Redactor, include_raw: bool = False):
        self.hermes_home = hermes_home
        self.redactor = redactor
        self.include_raw = include_raw

    def scan(self) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        commands: dict[str, dict[str, Any]] = {}
        raw_outputs: dict[str, str] = {}
        cron_text = ""
        for name, cmd in {
            "version": ["hermes", "--version"],
            "status": ["hermes", "status", "--all"],
            "doctor": ["hermes", "doctor"],
            "cron": ["hermes", "cron", "list"],
        }.items():
            code, out = run_cmd(cmd, timeout=45 if name == "doctor" else 20)
            commands[name] = {"exit_code": code, "available": code != 127}
            if name == "cron":
                cron_text = out
            if self.include_raw:
                raw_outputs[name] = self.redactor.redact(out[-4000:])
            if code not in {0, 127}:
                findings.append(Finding("warning", "runtime_gateway", f"runtime.{name}", f"Hermes command needs attention: {name}", f"exit={code}", "Run the command manually for details.").to_dict())
        log_dir = self.hermes_home / "logs"
        warning_count = 0
        error_count = 0
        if log_dir.exists():
            now = dt.datetime.now()
            window = dt.timedelta(hours=4)
            warning_events: set[str] = set()
            error_events: set[str] = set()
            benign = [re.compile(r"fallback", re.I), re.compile(r"sticky fallback IP", re.I)]
            for p in sorted(log_dir.glob("*.log"))[-5:]:
                for line in safe_read_text(p, max_bytes=500_000).splitlines()[-300:]:
                    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?\b(WARNING|ERROR|CRITICAL)\b\s+(.+)", line)
                    if not m:
                        continue
                    try:
                        ts = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    if now - ts > window:
                        continue
                    msg = self.redactor.redact(re.sub(r"\s+", " ", m.group(3)))
                    if any(pat.search(msg) for pat in benign):
                        continue
                    key = m.group(1) + "|" + hashlib.sha1(msg.encode()).hexdigest()[:12]
                    if m.group(2) in {"ERROR", "CRITICAL"} or re.search(r"traceback|timeout|401|403|429|refused", msg, re.I):
                        error_events.add(key)
                    else:
                        warning_events.add(key)
            warning_count = len(warning_events)
            error_count = len(error_events)
        if error_count > 5:
            findings.append(Finding("critical", "runtime_gateway", "gateway.errors", "Many recent runtime errors", f"error_events={error_count} warning_events={warning_count}", "Inspect recent Hermes logs locally.").to_dict())
        elif error_count > 0 or warning_count > 20:
            findings.append(Finding("warning", "runtime_gateway", "gateway.warnings", "Recent runtime warning/error events", f"error_events={error_count} warning_events={warning_count}", "Check whether timeouts or auth errors repeat.").to_dict())
        result: dict[str, Any] = {"commands": commands, "recent_error_events": error_count, "recent_warning_events": warning_count, "cron_text_for_internal_use": cron_text, "findings": findings}
        if self.include_raw:
            result["raw_outputs"] = raw_outputs
        return result


class SessionAnalyzer:
    def __init__(self, hermes_home: Path, redactor: Redactor):
        self.hermes_home = hermes_home
        self.redactor = redactor

    def scan(self) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        session_dir = self.hermes_home / "sessions"
        files = sorted(list(session_dir.glob("*.json")) + list(session_dir.glob("*.jsonl"))) if session_dir.exists() else []
        for p in files[-20:]:
            size = p.stat().st_size
            rel = self.redactor.redact(str(p))
            if size > 5 * 1024 * 1024:
                findings.append(Finding("critical", "session_context", "session.size", "Session file too large", f"{rel} size={size//1024}KB", "Review session rotation/compression.").to_dict())
            elif size > 1 * 1024 * 1024:
                findings.append(Finding("warning", "session_context", "session.size", "Session file size warning", f"{rel} size={size//1024}KB", "Check long-running or repeated context injection.").to_dict())
        return {"session_files": len(files), "findings": findings}


def sorted_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(findings, key=lambda f: (order.get(f.get("severity"), 9), f.get("domain", ""), f.get("code", "")))


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {sev: sum(1 for f in findings if f.get("severity") == sev) for sev in ["critical", "warning", "info"]}


def score_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    domains = {d: 100 for d in DOMAINS}
    for f in findings:
        domain = f.get("domain", "runtime_gateway")
        domains.setdefault(domain, 100)
        penalty = CRIT_PENALTY if f.get("severity") == "critical" else WARN_PENALTY if f.get("severity") == "warning" else 0
        domains[domain] = max(0, domains[domain] - penalty)
    mean = sum(domains.values()) / len(domains) if domains else 100
    min_score = min(domains.values()) if domains else 100
    return {"overall": int(0.4 * mean + 0.6 * min_score), "domains": domains}


def health_status_label(score: int, critical: int = 0, warning: int = 0) -> str:
    """A doctor that lists organ failure cannot also write 'healthy' on the chart.

    Critical and warning counts override the score-based label so the top-line
    cannot disagree with the severity tally. See score_findings for the score.
    """
    if critical >= 3 or score < 70:
        return "unhealthy"
    if critical >= 1 or warning >= 5 or score < 85:
        return "needs attention"
    return "healthy"


def public_scan(scan: dict[str, Any]) -> dict[str, Any]:
    """Remove internal-only data before JSON/report rendering."""
    clone = json.loads(json.dumps(scan, ensure_ascii=False))
    clone.get("runtime_gateway", {}).pop("cron_text_for_internal_use", None)
    return clone


def render_summary(scan: dict[str, Any], redactor: Redactor) -> str:
    scan = public_scan(scan)
    scores = scan["scores"]
    counts = severity_counts(scan["findings"])
    domains = ", ".join(f"{k}={v}" for k, v in scores["domains"].items())
    lines = [
        f"Hermes Health: {scores['overall']}/100 ({health_status_label(scores['overall'], counts['critical'], counts['warning'])})",
        f"Findings: critical={counts['critical']} warning={counts['warning']} info={counts['info']}",
        f"Domains: {domains}",
        f"Reminder/Cron: ids={scan.get('reminder_cron', {}).get('reminder_ids', [])}",
        f"Runtime: errors={scan.get('runtime_gateway', {}).get('recent_error_events', 0)} warnings={scan.get('runtime_gateway', {}).get('recent_warning_events', 0)}",
    ]
    actionable = [f for f in sorted_findings(scan["findings"]) if f.get("severity") in {"critical", "warning"}]
    if actionable:
        lines.append("Actionable:")
        for f in actionable[:5]:
            fid = f.get("id") or stable_id_for(f.get("code", ""))
            lines.append(f"- [{fid} {f['severity']}] {f['title']}: {f['evidence']}")
    else:
        lines.append("Actionable: none")
    return redactor.redact("\n".join(lines))


def render_report(scan: dict[str, Any], redactor: Redactor) -> str:
    scan = public_scan(scan)
    scores = scan["scores"]
    counts = severity_counts(scan["findings"])
    ordered = sorted_findings(scan["findings"])
    lines = [
        "# Hermes Doctor Health Report",
        "",
        "## Overall",
        f"- generated_at: {scan['generated_at']}",
        f"- score: {scores['overall']} / 100",
        f"- status: {health_status_label(scores['overall'], counts['critical'], counts['warning'])}",
        f"- findings: {len(scan['findings'])}",
        "",
        "## Domain Scores",
    ]
    for d, s in scores["domains"].items():
        lines.append(f"- {d}: {s}")
    lines += ["", "## Top Findings"]
    if not ordered:
        lines.append("- No findings above threshold.")
    for i, f in enumerate(ordered[:20], 1):
        fid = f.get("id") or stable_id_for(f.get("code", ""))
        conf = f.get("confidence") or confidence_for(f.get("code", ""))
        lines.append(f"{i}. [{fid}] [{f['severity'].upper()}] {f['title']} (confidence={conf})")
        lines.append(f"   - evidence: {f['evidence']}")
        lines.append(f"   - suggestion: {f['suggestion']}")
    lines += ["", "## Scanner Summary"]
    for key in ["markdown", "memory_skills", "reminder_cron", "session_context", "runtime_gateway"]:
        val = scan.get(key, {})
        compact = {k: v for k, v in val.items() if k not in {"findings", "raw_outputs"}}
        lines.append(f"- {key}: `{json.dumps(compact, ensure_ascii=False)}`")
    lines += [
        "",
        "## Safety Notes",
        "- Hermes Doctor v1 is observational and read-only.",
        "- It does not edit, delete, deduplicate, reconcile, or migrate state.",
        "- Raw command output is excluded by default; use --debug-raw only for local debugging.",
        "- Path, secret-like, and identifier-like strings are redacted on a best-effort basis.",
        "",
    ]
    return redactor.redact("\n".join(lines))


def build_scan(hermes_home: Path, include_paths: list[Path] | None = None, include_project_hub: bool = False, debug_raw: bool = False) -> dict[str, Any]:
    hermes_home = hermes_home.expanduser()
    redactor = Redactor(Path.home(), hermes_home)
    roots = [hermes_home / "memories", hermes_home / "skills"]
    if include_project_hub:
        roots.append(Path.home() / "projects-hub")
    for p in include_paths or []:
        roots.append(p.expanduser())
    markdown = MarkdownAnalyzer(roots, redactor).scan()
    memory_skills = MemorySkillsAnalyzer(hermes_home, redactor).scan()
    runtime = RuntimeAnalyzer(hermes_home, redactor, include_raw=debug_raw).scan()
    reminder = ReminderCronChecker(hermes_home / "memories" / "REMINDERS.md", runtime.get("cron_text_for_internal_use", ""), redactor).scan()
    session = SessionAnalyzer(hermes_home, redactor).scan()
    findings: list[dict[str, Any]] = []
    for part in [markdown, memory_skills, runtime, reminder, session]:
        findings.extend(part.get("findings", []))
    return {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "markdown": markdown,
        "memory_skills": memory_skills,
        "runtime_gateway": runtime,
        "reminder_cron": reminder,
        "session_context": session,
        "findings": findings,
        "scores": score_findings(findings),
    }


def write_report_files(hermes_home: Path, report: str) -> Path:
    outdir = hermes_home.expanduser() / "reports" / "health"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"hermes_doctor_{stamp}.md"
    if out.exists():
        out = outdir / f"hermes_doctor_{stamp}_{dt.datetime.now().strftime('%f')}.md"
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(report, encoding="utf-8")
    os.replace(tmp, out)
    latest = outdir / "latest.md"
    latest_tmp = outdir / f".latest.{os.getpid()}.tmp"
    shutil.copy2(out, latest_tmp)
    os.replace(latest_tmp, latest)
    return out


def exit_code_for(scan: dict[str, Any], fail_on: str) -> int:
    if fail_on == "never":
        return 0
    counts = severity_counts(scan["findings"])
    if fail_on == "warning" and (counts["critical"] or counts["warning"]):
        return 2
    if fail_on == "critical" and counts["critical"]:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Hermes Doctor: read-only health scanner for Hermes Agent")
    ap.add_argument("--hermes-home", default=str(Path.home() / ".hermes"))
    ap.add_argument("--include", action="append", default=[], help="Additional Markdown path to scan (opt-in; repeatable)")
    ap.add_argument("--include-project-hub", action="store_true", help="Opt-in scan of ~/projects-hub")
    ap.add_argument("--json", action="store_true", help="Print safe JSON instead of Markdown")
    ap.add_argument("--summary", action="store_true", help="Print compact operational summary")
    ap.add_argument("--write-report", action="store_true", help="Write report under <HERMES_HOME>/reports/health and refresh latest.md")
    ap.add_argument("--fail-on", choices=["never", "critical", "warning"], default="never", help="Exit 2 if findings meet threshold")
    ap.add_argument("--debug-raw", action="store_true", help="Include redacted raw command output in JSON/report; local debugging only")
    args = ap.parse_args(argv)
    hermes_home = Path(args.hermes_home).expanduser()
    redactor = Redactor(Path.home(), hermes_home)
    scan = build_scan(hermes_home, [Path(p) for p in args.include], args.include_project_hub, args.debug_raw)
    if args.json:
        print(redactor.redact(json.dumps(public_scan(scan), ensure_ascii=False, indent=2)))
    elif args.summary:
        print(render_summary(scan, redactor))
    else:
        report = render_report(scan, redactor)
        print(report)
        if args.write_report:
            out = write_report_files(hermes_home, report)
            print(f"\nREPORT_WRITTEN={redactor.redact(str(out))}")
            print(f"REPORT_LATEST={redactor.redact(str(out.with_name('latest.md')))}")
    return exit_code_for(scan, args.fail_on)


if __name__ == "__main__":
    raise SystemExit(main())
