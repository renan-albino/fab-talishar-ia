---
name: automate-repetitive-tasks
description: Find tasks that repeat across sessions and turn them into scripts in automated-tasks/scripts/.
disable-model-invocation: true
---

# Automate repetitive tasks

Turn the work that keeps getting done by hand into scripts under `automated-tasks/scripts/`, indexed in the `automated-tasks` skill.

## 1. Find candidates

Analyze the sessions and workspace for tasks that were, or might be, repetitive:

- Inspect recent session transcripts, `graphify-out/`, or search command patterns via `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia git grep -n "<termo>"`.
- Flag repeated commands, repeated manual sequences, and one-off steps likely to recur.
- For each candidate, check `.agents/skills/automated-tasks/SKILL.md`: is it already automated, or does an existing script need adjusting?

**Done when:** every candidate is classified — new script, adjust existing, or already covered.

## 2. Present and await

Show the user the candidates: the task, how often it appears, and your recommendation for each. Await the user's instructions; write nothing before the user picks.

## 3. Build the chosen tasks

For each task the user chose, create or update a Python script in `.agents/skills/automated-tasks/scripts/`, updating `.agents/skills/automated-tasks/SKILL.md` as you go:

- The script must run via WSL2 Python/PyTorch environment: `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/<script>.py`.
- Support `--help` (`-h`) and `--json` for structured telemetry.
- Keep it small and single-purpose (Ponytail standard).

**Done when:** each chosen task has a script that runs via `./venv/bin/python` (verify with `-h` and `--json`) and a row in `.agents/skills/automated-tasks/SKILL.md`.
