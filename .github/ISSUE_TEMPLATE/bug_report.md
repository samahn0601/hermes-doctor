---
name: Bug report
about: Hermes Doctor reported something wrong, crashed, or leaked something it shouldn't
title: "[bug] "
labels: bug
---

> ⚠️ **Before pasting any output, read [SECURITY.md](../../SECURITY.md).**
> Do not paste raw memory files, raw skill files, raw cron commands,
> absolute home paths, or `--debug-raw` output in a public issue. Prefer
> `--summary` or `--json`, then re-read it for anything personal and
> replace with `<redacted>` by hand.

## Environment

- Hermes Doctor version (`pip show hermes-doctor`):
- OS:
- Python version (`python --version`):
- Install method (pipx / pip / source):

## Command run

```
hermes-doctor ...
```

## What I expected

<!-- one or two sentences -->

## What happened

<!-- one or two sentences -->

## Redacted output

<!--
Paste the redacted summary or JSON here. Stable finding IDs (HD-MD-001,
HD-MEM-002, …) are very helpful — see FINDING_IDS in src/hermes_doctor/cli.py.
-->

```
```

## Anything else?

<!-- Optional: edge cases, the kind of Hermes home that triggers this, etc. -->
