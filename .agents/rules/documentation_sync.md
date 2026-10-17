---
trigger: always_on
description: Mandatory documentation synchronization (Zero Doc Drift) across README.md, CONTEXT.md, docs/ROADMAP.md, ADRs, and setup_templates/.
---

# Documentation Synchronization & Zero Drift

Rule:
- **Mandatory Documentation Synchronization (Zero Doc Drift)**: Whenever modifying code, refactoring modules, adding scripts, altering command-line flags, updating model architecture, or tweaking combat rules:
  1. **PROACTIVELY UPDATE `.md` DOCUMENTATION**: Always update the relevant `.md` documentation files (`README.md`, `CONTEXT.md`, `docs/ROADMAP.md`, and `docs/adr/`) before finishing the response or running commit/push.
  2. **ACCURATE METRICS**: Keep exact counts and metrics (unit test counts via `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python -m pytest --collect-only -q`, hero strategy counts, card database counts) 100% aligned with reality. Never use unquoted `|` in PowerShell when invoking WSL commands (use multiple `-e` in `git grep`).
  3. **NEW ARCHITECTURAL TERMS**: Register any new terminology, facades, or major scripts immediately in `CONTEXT.md` and `docs/adr/`.
  4. **TEMPLATES DRIFT**: If modifying `Talishar-FE/` or `Talishar/`, always re-export templates (`wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python scripts/prepare_environment.py --export-templates`) and ensure `setup_templates/` has no uncommitted diff.
  5. **KNOWLEDGE GRAPH SYNC**: After modifying code files, run `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia bash -c "test -x ./venv/bin/graphify && ./venv/bin/graphify update . || true"` and `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py`.
