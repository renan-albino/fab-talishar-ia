# Documentation Synchronization & Zero Drift

Rule:
- **Mandatory Documentation Synchronization (Zero Doc Drift)**: Whenever modifying code, refactoring modules, adding scripts, altering command-line flags, updating model architecture, or tweaking combat rules:
  1. **PROACTIVELY UPDATE `.md` DOCUMENTATION**: Always update the relevant `.md` documentation files (`README.md`, `CONTEXT.md`, `docs/ROADMAP.md`, and `docs/`) before finishing the response or running commit/push.
  2. **ACCURATE METRICS**: Keep exact counts and metrics (unit test counts, hero strategy counts, card database counts) 100% aligned with reality.
  3. **NEW ARCHITECTURAL TERMS**: Register any new terminology, facades, or major scripts immediately in `CONTEXT.md`.
  4. **TEMPLATES DRIFT**: If modifying `Talishar-FE/` or `Talishar/`, always re-export templates (`scripts/prepare_environment.py --export-templates`) and ensure `setup_templates/` has no uncommitted diff.
  5. Never complete a task leaving stale documentation that would cause future agents to make false assumptions.
