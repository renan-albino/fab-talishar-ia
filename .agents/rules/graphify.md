---
trigger: always_on
description: Consult the graphify knowledge graph at graphify-out/ for codebase and architecture questions.
---

## graphify

This project has a graphify knowledge graph at `graphify-out/`.

Rules:
- For codebase or architecture questions, when `graphify-out/graph.json` exists, you can query the graph directly or, if the CLI is installed in the venv, run `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia bash -c "test -x ./venv/bin/graphify && ./venv/bin/graphify query '<question>' || true"` (CLI) or `query_graph` (MCP). If `graphify` CLI is not installed, inspect `graphify-out/GRAPH_REPORT.md` and `graphify-out/graph.json`.
- Never pass unquoted `|` in PowerShell commands invoking WSL (`git grep` or `graphify`); if searching multiple terms with `git grep`, use multiple `-e` flags (`git grep -n -e "termA" -e "termB"`).
- If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files.
- Read `graphify-out/GRAPH_REPORT.md` for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code files in this session, run `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia bash -c "test -x ./venv/bin/graphify && ./venv/bin/graphify update . || true"` to keep the graph current when installed.
