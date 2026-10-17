---
trigger: always_on
description: Multi-agent orchestration protocol defining strict subagent roles, File Ownership Lock, and Zero Polling reactive wakeup.
---

# Multi-Agent Orchestration & File Ownership Rule

Rule:
- **Parallel Subagent Delegation**: Whenever a task spans multiple independent modules, large codebase audits, concurrent refactorings, or parallel documentation/test suites, delegate concurrently via a single `invoke_subagent` call (`Model="inherit"`).
- **Strict Specialized Roles**:
  1. **`Codebase Researcher`** (`TypeName="research"`): Read-only exploration, `git grep -n` (using multiple `-e` instead of unquoted `|` in PowerShell), and `graphify` queries. Returns exact `file:line` references and root-cause summaries.
  2. **`Refactor Specialist`** (`TypeName="self"`): Surgical code/documentation edits (`replace_file_content` / `write_to_file`) under Ponytail Protocol (YAGNI, minimal diff, zero boilerplate).
  3. **`Test & Quality Runner`** (`TypeName="self"`): Executes smoke tests (`run_smoke_tests.py`), `pytest`, `benchmark_mcts.py`, `diagnose_sim2real.py`, and `graphify update .` via `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia`.
- **File Ownership Lock (Anti-Collision)**:
  - Each active `Refactor Specialist` MUST be assigned an explicit, disjoint list of target files.
  - Subagents MUST NOT edit any file outside their assigned ownership list to prevent merge/write collisions.
- **Zero Polling (Reactive Wakeup)**:
  - Never poll `manage_subagents` or `manage_task` in a loop after spawning subagents or background tasks.
  - Stop calling tools to end the turn and let the reactive messaging system wake the orchestrator upon completion.
