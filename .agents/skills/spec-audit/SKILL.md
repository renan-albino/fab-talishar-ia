---
name: spec-audit
description: >-
  Audit a feature's documents (spec, tickets, and the ADRs and glossary they cite) along two axes — Standards (do the docs follow the repo's documented standards: ADR contracts, glossary terms, tracker conventions?) and Spec (do the tickets faithfully decompose the spec?). Runs both audits in parallel sub-agents and reports them side by side. Use after to-spec or to-tickets publishes docs, when the user wants to review a spec or its tickets, or asks to "audit the spec" / "check the tickets against the ADRs".
---

Two-axis audit of a feature's documents — the spec, its tickets, and the ADRs and glossary they cite:

- **Standards** — do the docs conform to this repo's documented standards (ADR contracts, glossary, tracker conventions)?
- **Spec** — do the tickets faithfully decompose the originating spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings. If subagents aren't available — or the user asks to run without them — run both axes **inline in this session** instead (Standards first, then Spec) with the same briefs from step 3; the reports still land under separate `## Standards` / `## Spec` headings, so the two-axis separation holds even without the parallelism.

The issue tracker should have been provided to you — run `/setup-matt-pocock-skills` if `docs/agents/issue-tracker.md` is missing.

## Process

### 1. Pin the target

The spec the user names — a path, a feature slug (→ `.scratch/<feature-slug>/spec.md`), or "the spec we just wrote". If they didn't specify one, ask for it.

Collect the doc set: the spec, every ticket in its `issues/` directory, `CONTEXT.md`, and every ADR the spec or tickets cite. Confirm the spec exists and note whether tickets are present (their absence means the Spec axis is skipped — see step 3). A missing spec should fail here — not inside two parallel sub-agents.

### 2. Identify the standards sources

Anything in the repo that documents how this repo's documents should be written, such as:

- `docs/adr/*.md` — ADR contracts, especially the ones the doc set cites
- `CONTEXT.md` — the glossary: canonical terms and their `_Avoid_` lists
- `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md` — tracker conventions (one directory per feature, file naming, `Status:` lines, label strings)
- `AGENTS.md` — repo rules
- the format contracts the documents themselves reference (the ADR and glossary formats the domain-modeling skill points at)

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of documentation smells that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Mangled Contract"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the doc set:

- **Mangled Contract** — a doc paraphrases an ADR's contract and drops a required element (a three-part facade contract reduced to "a one-paragraph summary"). → quote the ADR's contract in full; restore the dropped element.
- **Term Drift** — a doc uses a word the glossary defines differently, or a word on a term's `_Avoid_` list. → use the canonical term.
- **Orphan Requirement** — a spec requirement no ticket covers. → add a ticket, or an explicit deferral in the spec's Out of Scope.
- **Scope Leak** — a ticket promises what the spec marks Out of Scope. → cut it, or cite the spec line that licenses it.
- **Phantom Coverage** — a ticket appears to cover a requirement, but its wording covers a shadow of it. → reword the criterion against the spec's wording.
- **Unfalsifiable Criterion** — an acceptance checkbox no test could fail ("the API is clean"). → sharpen it to a checkable condition.
- **Stale Cross-Reference** — a pointer to an ADR, ticket, or spec section that doesn't exist or has changed. → fix or delete the reference.

### 3. Spawn both sub-agents in parallel

**Standards sub-agent prompt** — include:

- The doc set to audit (spec path, ticket paths, `CONTEXT.md`, the cited ADRs).
- The list of standards-source files you found in step 2, **plus the smell baseline from step 2 pasted in full** — the sub-agent has no other access to it.
- The brief: "Report — per document and section where relevant — (a) every place the docs violate a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the doc sentence. Distinguish hard violations from judgement calls — documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces (generated files like `CRATES.md`). Under 400 words."

**Spec sub-agent prompt** — include:

- The spec path and the ticket paths — the spec is the reference; the tickets are the material under audit.
- The brief: "Report: (a) requirements the spec asked for that the tickets miss or cover only partially; (b) content in the tickets that the spec didn't ask for (scope creep); (c) requirements that look covered but where the ticket's wording is wrong or misleading. Quote the spec line for each finding. Under 400 words."

If the spec has no tickets yet, skip the Spec sub-agent and note this in the final report.

### 4. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

## Why two axes

A doc set can pass one axis and fail the other:

- Docs that follow every ADR and glossary rule but miss the spec's requirements → **Standards pass, Spec fail.**
- Tickets that faithfully decompose the spec but violate an ADR's contract or the glossary → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
