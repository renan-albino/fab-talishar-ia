---
name: fill-skill-gaps
description: Analyze the session for API knowledge gaps, check the family skills and their references/ folders, and add a missing topic reference (or a new singleton/family) for an API the agent struggled with.
---

The user invoked this skill to fill gaps in the skill library based on what the agent struggled with during the session.

## The model

Code-related knowledge lives in **family skills** — one skill per language or framework, each with a `references/` folder of topic files (`references/<topic>.md`). A single library or crate can be a **standalone singleton** — its own skill. A gap is therefore one of: **a missing topic reference inside an existing family**, **a missing singleton skill**, or **a brand-new family**. Check first (Step 2); only create what is genuinely absent.

## Coding Guidelines

Every change in this repo follows the repo's coding guidelines (see AGENTS.md). They bind code and code examples, not Markdown files.

## Step 1: Detect API Knowledge Gaps

Scan the conversation history for signs the agent was struggling with an API it didn't have a reference for. Look for:

- **Repeated searches** for the same API, module, or crate (multiple `search_graph`, `search_code`, `rg`, or `webfetch` calls targeting the same topic)
- **Source code exploration** of framework or crate internals (reading a crate's or framework's source to understand how something works)
- **Web searches** for API documentation (for framework or crate API docs)
- **Confusion signals** — the agent asking the user how an API works, or expressing uncertainty about an API's behavior
- **Trial-and-error patterns** — multiple attempts to use an API incorrectly before finding the right approach

Group findings by **topic** and note which **family** each belongs to (e.g. a framework family → a topic within it; the language family → a build tool or standard library).

## Step 2: Check Existing

For each topic identified, check whether a reference already covers it:

1. Find the home — a family or a singleton.
2. Look for a topic file — `<family>/references/<topic>.md`, or the singleton's `SKILL.md`. Read it and assess whether it covers the missing information.
3. If a reference exists but is incomplete, note it for augmentation (skip creation).
4. **Verify the names too** — an existing reference whose API names (traits, structs, functions, prelude claims) do not exist in the version pinned in the repo manifest (e.g. `Cargo.toml`) is a *correctness* gap, not just a completeness gap. Verify with the Name Verification Gate (Step 3) and fix the stale names.

## Step 3: Create the Missing Reference

For each topic with no covering reference (or a new singleton/family):

### Run each topic as a parallel sub-agent

Each missing topic is an **independent unit** — its research, name verification, and drafting don't touch the other topics. So when there is more than one, **spawn one sub-agent per topic, in parallel**: give each a self-contained brief (the pinned version, the Coding Guidelines above, the "Research the API" + "Name Verification Gate" + the format/content rules below, and the target path, e.g. `<family>/references/<topic>.md`) and ask it to return the drafted reference **plus** its Name-Verification evidence and any "needs verification" list. This keeps the deep per-crate research out of the main context and lets several references land at once. Collect the drafts and continue with Steps 4 and 5 in the main session. If subagents aren't available — or the user asks to run without them — do the topics inline in this session, one at a time.

### Research the API

Anchor everything to the versions the project pins:

1. **Pinned versions first** — read them from the workspace manifest (e.g. the root `Cargo.toml`). The family `SKILL.md`'s version pin must match.
2. **Crate source of that exact version** — preferred: the codebase-memory project named after the version (`list_projects` → e.g. `<crate>-<version>`) via `search_graph` / `search_code`; fallback: `rg` over the version-pinned checkout. Follow this repo's AGENTS.md rules for where to source external code.
3. **Official docs** — only at the pinned version, never unversioned "latest". Docs describe the API surface; the names still need source verification (next section).

Focus on what the agent was actually struggling with, but build the reference as a **comprehensive topic reference**, not just the missing piece.

### Re-verifying an existing reference after source changes

When a reference already covers a topic but its source has changed significantly (a tool added or renamed, a parameter or error-code set changed, an endpoint setting moved), **update that reference** rather than leaving it stale — the gap is now a *correctness* gap, the same kind as a stale name. This is the "exists but incomplete" case from Step 2 resolved by editing, not by skipping.

For external crates or libraries, the Name Verification Gate below applies — verify against the pinned version's source.

After the edit, re-check the Step 5 report row: "all names resolve against the facade" or the specific facade claims fixed.

### Name Verification Gate (mandatory before writing)

Before writing the reference file, verify **every** API name it will mention (traits, structs, enums, functions, methods, macros, module paths) against the pinned version's source:

1. `search_graph` (version-named project) or `rg` over the pinned checkout — the name must resolve to a real definition (or a re-export) **in that version**.
2. Placement claims ("in the crate prelude", "in module X") — read that version's actual prelude module / module declarations and confirm.
3. If a name only resolves in a *different* version, it must not be written — even if it is a name you "know" from an older release. This is exactly how stale names leak into references and cause compile errors in the session that follows.
4. Record the evidence (project / `file:line`) — it feeds the Step 5 report.

### Reference Format

A reference is **plain Markdown** — no frontmatter (the family `SKILL.md` carries the version pin). See existing topic references in a family's `references/` folder as templates:

```markdown
# <Topic> (<crate, if external>)

<one-line scope of the topic>

## <Section 1>

<content with code examples>

## <Section 2>

<content with code examples>
```

### Reference Content Rules

- **No frontmatter**: the file is plain Markdown; the family `SKILL.md`'s `metadata` carries the version pin
- **Version-anchored names**: every API name must pass the Name Verification Gate against the pinned version — no names from memory or from other versions' docs
- **Sections**: cover construction, key methods, common patterns, configuration, and pitfalls
- **Code examples**: idiomatic code for the project's language, using the pinned APIs
- **Tables**: for method summaries, type comparisons, or option enums
- **No commentary**: reference-only, no "you should" or "best practice" prose
- **Cross-references**: intra-family → `references/<topic>.md`; cross-family → name the family and topic (e.g. "the `<family>` skill's `<topic>` reference")
- **Length**: compact but complete — aim for 80–200 lines

### Writing the Reference

1. Create `<family>/references/<topic>.md` (a new singleton is its own `<name>/SKILL.md`)
2. Write the reference following the format above
3. Add a row to the family's `SKILL.md` `## References` table pointing at `references/<topic>.md` with a one-line summary of what it covers
4. Do NOT create a command file — only the reference (and, for a brand-new family, its `SKILL.md` index)

## Step 4: Update the family's index

Process skills that carry a per-family Code table hold **one row per family** (not per reference), so a new reference inside an existing family needs **no** change to them. What does need updating:

- **The family's `SKILL.md` `## References` table** — add the new `references/<topic>.md` row (Step 3.3).
- **The family's `SKILL.md` frontmatter `description`** — only if the new topic is a headline capability not already implied.
- **A brand-new family or singleton** — add one row to each process skill's Code table (alphabetical).

## Step 5: Report

Summarize what was found and what was created:

| Topic | Family | Gap Detected | Reference Exists | Action | Names Verified Against |
|---|---|---|---|---|---|
| `<topic>` | `<family>` | repeated searches for X | No | Created `<family>/references/<topic>.md` + row | `<crate>-<version>` — `file:line` of key definitions |
| `<topic>` | `<family>` | source exploration | Yes (incomplete) | Augmented `<family>/references/<topic>.md` | `<crate>-<version>` — stale names found/fixed, or "all names resolve" |

Also note whether any process-skill table needed a new family/singleton row. If no gaps were detected, report that the skill library covers the session's needs.
