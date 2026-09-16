---
name: automate-repetitive-tasks
description: Find tasks that repeat across sessions and turn them into scripts in automated-tasks/scripts/.
disable-model-invocation: true
---

# Automate repetitive tasks

Turn the work that keeps getting done by hand into scripts under `automated-tasks/scripts/`, indexed in the `automated-tasks` skill.

## 1. Find candidates

Analyze the sessions for tasks that were, or might be, repetitive:

- Read this workspace's session history from `~/.local/share/opencode/opencode.db` (SQLite): `session` rows whose `directory` is this repo, then `message` and `part` (their `data` is JSON) for what actually happened. Recent sessions first.
- Flag repeated commands, repeated manual sequences, and one-off steps likely to recur.
- For each candidate, check `automated-tasks/SKILL.md`: is it already automated, or does an existing script need adjusting?

**Done when:** every candidate is classified — new script, adjust existing, or already covered.

## 2. Present and await

Show the user the candidates: the task, how often it appears, and your recommendation for each. Await the user's instructions; write nothing before the user picks.

## 3. Build the chosen tasks

For each task the user chose, create or update a Python script in `automated-tasks/scripts/`, updating `automated-tasks/SKILL.md` as you go:

- The script must run with `uv run` (PEP 723 header: `requires-python`, `dependencies`).
- Running the script with no args or with `-h` shows its help and possible args.
- Keep it small and single-purpose.

**Done when:** each chosen task has a script that runs (verify with its help path) and a row in `automated-tasks/SKILL.md`.
