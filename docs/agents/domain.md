# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root: The canonical glossary for all domain concepts, rules, and architecture terms, including explicit `_Avoid_` constraints to prevent terminological drift.
- **`docs/adr/`**: Read the Architectural Decision Records (ADRs) that touch the area you are about to work in:
  - [ADR-0001-modular-package-decomposition.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0001-modular-package-decomposition.md): Decomposição dos 9 monólitos em pacotes coesos (`ai/bot_runtime/`, `ai/policy/`, `ai/mcts/`, `ai/training/`, `deck_manager/`, `stats/`, `ui/`) mantendo fachadas retrocompatíveis.
  - [ADR-0002-parallel-ismcts-multithreading.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0002-parallel-ismcts-multithreading.md): Paralelização do ISMCTS através de determinizações independentes de mundos concorrentes com `ThreadPoolExecutor`.
  - [ADR-0003-concurrent-atomic-persistence-file-locks.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0003-concurrent-atomic-persistence-file-locks.md): Persistência atômica segura (`atomic_json_save`) e mutex interprocessos via `fcntl.flock` reentrante (`ai/atomic_io.py`).
  - [ADR-0004-arsenal-cr315-and-digging-mode.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0004-arsenal-cr315-and-digging-mode.md): Poda estrita de Arsenal conforme CR 3.1.5 e Heurística de Modo Cavar (CR 4.3.2) para desobstrução de mãos travadas.
  - [ADR-0005-setup-templates-vs-git-submodules.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0005-setup-templates-vs-git-submodules.md): Desacoplamento via `setup_templates/` contra forks/submódulos do Talishar para imunidade a quebras upstream.
  - [ADR-0006-asymmetric-distillation-mcts-visit-targets.md](file:///home/renan-albino/Documents/fab-talishar-ia/docs/adr/ADR-0006-asymmetric-distillation-mcts-visit-targets.md): Distilação assimétrica usando vetor de visitas ISMCTS ($\pi_{\text{MCTS}}$) e alvos auxiliares KataGo.

## File structure

Single-context layout:

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── ADR-0001-modular-package-decomposition.md
│   ├── ADR-0002-parallel-ismcts-multithreading.md
│   ├── ADR-0003-concurrent-atomic-persistence-file-locks.md
│   ├── ADR-0004-arsenal-cr315-and-digging-mode.md
│   ├── ADR-0005-setup-templates-vs-git-submodules.md
│   └── ADR-0006-asymmetric-distillation-mcts-visit-targets.md
├── ai/
│   ├── bot_runtime/         ← client, lobby, match tracker, choices, phases
│   ├── policy/              ← attack, defense, pitch, arsenal pruners & engine
│   ├── mcts/                ← node, standard_mcts, world_generator, ismcts
│   ├── training/            ← orchestrator, matchup_engine, process_supervisor
│   ├── hero_strategies/     ← 139 heróis, knapsack_solver, turn_planner
│   └── atomic_io.py         ← atomic_json_save & file_lock
├── deck_manager/            ← parser, repository, slugifier, validator
├── stats/                   ← elo, storage, sync, deck_names
└── ui/                      ← dashboard Streamlit decomposto (helpers e tabs/)
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids in its `_Avoid_` annotations.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output or refactor proposal contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-NNNN (...), but worth reopening because…_
