# Multi-Agent Relationship & Sync Health Diagnostics Implementation Plan

> **For Hermes:** Use this plan to add inter-bot health, deadlock, and infinite loop traps checks to both `hermes-doctor` and `openclaw-doctor` repositories.

**Goal:** Implement robust static and dynamic checks to detect multi-bot configuration traps, token reuse, infinite loop exposure, and handoff deadlocks.

**Architecture:**
- **`openclaw-doctor`**: Introduce a new domain `bots` containing `OC-BOT-001` (loop risk), `OC-BOT-002` (handoff deadlock/quarantine), and `OC-BOT-003` (shared channel pollution).
- **`hermes-doctor`**: Extend `cli.py` with a new group `multi_agent` containing `HD-BOT-001` (token reuse collision), `HD-BOT-002` (cron task congestion), and `HD-BOT-003` (agent bridge daemon heartbeat).

**Tech Stack:** Python 3.10/3.11/3.12, Pytest, Ruff.

---

## Part 1: openclaw-doctor (Bots Domain Expansion)

### Task 1: Define Finding Codes in openclaw-doctor
**Objective:** Add `OC-BOT-001`, `OC-BOT-002`, and `OC-BOT-003` definitions to `openclaw_doctor/findings.py`.
**Files:**
- Modify: `src/openclaw_doctor/findings.py`
- Test: `tests/test_findings.py`

**Step 1.1: Edit `findings.py`**
Add the following entries:
```python
    "OC-BOT-001": FindingDefinition(
        code="OC-BOT-001",
        severity="critical",
        title="Infinite loop risk: allowBots is true and requireMention is false",
        suggestion="Set allowBots to 'mentions' or requireMention to true for shared channels to avoid infinite bot-to-bot loops.",
    ),
    "OC-BOT-002": FindingDefinition(
        code="OC-BOT-002",
        severity="warning",
        title="Agent Bridge handoff blockage or quarantine",
        suggestion="Review stale handoff files under OneDrive/openclaw/ bridging directory.",
    ),
    "OC-BOT-003": FindingDefinition(
        code="OC-BOT-003",
        severity="warning",
        title="Overlapping client identities or shared channel pollution",
        suggestion="Ensure distinct mention requirements or custom prefixes for overlapping bots.",
    )
```

**Step 1.2: Run pytest to ensure findings are registered**
Run: `pytest tests/test_findings.py -v`
Expected: PASS

---

### Task 2: Implement static configuration linter rules in openclaw-doctor
**Objective:** Write parsing and inspection heuristics in a new config inspection module.
**Files:**
- Create: `src/openclaw_doctor/domains/bots.py`
- Test: `tests/test_bots_domain.py`

**Step 2.1: Write `src/openclaw_doctor/domains/bots.py`**
```python
import json
from pathlib import Path
from typing import Any
from openclaw_doctor.findings import Finding

class BotsAnalyzer:
    def __init__(self, root: Path):
        self.root = root

    def scan(self) -> list[Finding]:
        findings = []
        config_path = self.root / "openclaw.json"
        if not config_path.exists():
            return findings

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return findings

        # Heuristic 1: Loop trap check (OC-BOT-001)
        # Parse platforms or profiles inside openclaw.json
        platforms = config.get("platforms", {})
        allow_bots_global = config.get("allowBots", False)
        
        for name, plat in platforms.items():
            allow_bots = plat.get("allowBots", allow_bots_global)
            require_mention = plat.get("requireMention", False)
            if allow_bots is True and require_mention is False:
                findings.append(Finding(
                    code="OC-BOT-001",
                    evidence=f"platform {name} allowBots=true and requireMention=false",
                ))

        # Heuristic 2: OneDrive/Agent Bridge handoff blocks (OC-BOT-002)
        # Check standard OneDrive path for bridging
        bridge_path = Path("/Users/ansang2/Documents/OneDrive/2026/AI/openclaw")
        if bridge_path.exists():
            import datetime
            stale_threshold = datetime.datetime.now() - datetime.timedelta(days=2)
            for file in bridge_path.glob("*.md"):
                try:
                    mtime = datetime.datetime.fromtimestamp(file.stat().st_mtime)
                    if mtime < stale_threshold:
                        content = file.read_text(encoding="utf-8", errors="ignore")
                        if "medical:true" in content and "signoff_by:null" in content:
                            findings.append(Finding(
                                code="OC-BOT-002",
                                evidence=f"Stale bridge file {file.name} (last modified {mtime})",
                            ))
                except Exception:
                    pass

        return findings
```

---

## Part 2: hermes-doctor (Multi-Agent Token & Sync Checks)

### Task 3: Define Finding Codes in hermes-doctor
**Objective:** Add `HD-BOT-001`, `HD-BOT-002`, and `HD-BOT-003` to `hermes_doctor/cli.py`.
**Files:**
- Modify: `src/hermes_doctor/cli.py`
- Test: `tests/test_cli.py`

**Step 3.1: Register stable IDs**
```python
    "bot.token_collision": "HD-BOT-001",
    "bot.cron_concurrency": "HD-BOT-002",
    "bot.bridge_heartbeat": "HD-BOT-003",
```
And add matching confidence mappings:
```python
    "bot.token_collision": "high",
    "bot.cron_concurrency": "medium",
    "bot.bridge_heartbeat": "high",
```

**Step 3.2: Implement `MultiAgentAnalyzer`**
Add an analyzer scanning `.env` profiles and active gateway configurations for:
- Duplicated `TELEGRAM_BOT_TOKEN` or overlaps across `profiles/` env files.
- Identical runtimes in cron schedules.
- Freshness of `~/.openclaw/extensions/strip-think-tags/loop-state.json` or bridge state outputs.
