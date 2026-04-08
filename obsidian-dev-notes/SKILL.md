---
name: obsidian-dev-notes
description: >
  Manages structured developer knowledge in Obsidian using atomic typed notes, Maps of Content (MOCs),
  and bi-directional wikilinks. Use this skill whenever a developer or dev team needs to: start a new
  project in Obsidian, document an architectural or technical decision, capture a reusable pattern,
  record a learning or insight, run a weekly review of their vault, search for existing knowledge before
  creating new notes, or maintain a project MOC. Also triggers for: "add this to my notes", "document
  this decision", "create a project hub", "update my Obsidian", "capture this pattern", "link this to
  my project". If the user mentions ingesting raw sources, external documents, PDFs, GitHub repos, or
  says anything about "raw folder", "ingest", or "RAG", STOP and read references/karpathy-ingest.md
  before proceeding — that workflow is handled separately.
---

# Obsidian Developer Notes

You are managing a developer's Obsidian knowledge base. Your job is to write and maintain structured,
interconnected notes that compound in value over time. Notes are atomic, typed, and always linked
back to related concepts and project hubs.

---

## Vault Folder Schema

```
vault/
├── Projects/       ← one MOC per project (the hub)
├── Decisions/      ← architectural and technical decisions
├── Patterns/       ← reusable solutions worth documenting
├── Learnings/      ← concepts, insights, things discovered
├── Retrospectives/ ← post-project or sprint reviews
├── Inbox/          ← quick captures, processed during weekly review
├── raw/            ← external source material (articles, PDFs, repos)
└── wiki/           ← LLM-compiled synthesis from raw/ (Karpathy ingest)
```

**Route every note to its folder based on `type` frontmatter.** If unsure where something belongs,
prefer `Learnings/` for concepts and `Decisions/` for choices.

---

## Frontmatter Schema by Note Type

Every note gets typed frontmatter. This enables powerful vault-wide queries later.

### MOC (Project Hub)
```yaml
---
type: moc
project: <kebab-case-project-name>
status: planning | in-progress | completed | archived
tags: [project, <domain>, <tech-stack>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Decision
```yaml
---
type: decision
project: <project-name>
decision-status: proposed | accepted | rejected | deprecated
tags: [decision, <category>]
created: YYYY-MM-DD
---
```

### Pattern
```yaml
---
type: pattern
tags: [pattern, <category>, <tech>]
created: YYYY-MM-DD
---
```

### Learning
```yaml
---
type: learning
project: <project-name>   ← optional, omit if general
tags: [learning, <concept>]
created: YYYY-MM-DD
---
```

### Retrospective
```yaml
---
type: retrospective
project: <project-name>
tags: [retrospective, project-complete]
created: YYYY-MM-DD
---
```

---

## Core Principle: Search Before Creating

Before writing any new note, always search the vault first. This prevents duplication and reveals
existing knowledge to link to.

```
1. obsidian_omnisearch(query) — fuzzy search by topic/keywords
2. Review results:
   - Exact match found → link to it, don't duplicate
   - Related notes found → create new note but link to findings
   - Nothing found → create fresh atomic note
```

This is the step most often skipped and the one that makes the biggest long-term difference.
Every note you link to an existing one makes both more discoverable.

---

## Workflows

### New Project

1. Search for related past projects: `obsidian_omnisearch("<tech> <domain> project")`
2. Create the MOC: `obsidian_write_note("Projects/<ProjectName>-MOC.md", content)`
3. Use placeholder wikilinks `[[Decision: Topic]]` for known upcoming decisions
4. Link to any related past projects found in step 1

**MOC body template:**
```markdown
# <Project Name> - Project MOC

## Overview
[One paragraph description]

## Key Concepts
- [[Concept 1]]

## Architecture Decisions
- [[Decision: <Topic>]]

## Implementation Notes

## Learnings

## Related Projects
- [[<Past Project>-MOC]]
```

### Document a Decision

1. Search for existing decisions on the same topic
2. Create: `obsidian_write_note("Decisions/<ProjectName>-<Decision>.md", content)`
3. Patch the project MOC to link to the new decision:
   `obsidian_patch_note("Projects/<ProjectName>-MOC.md", operation="append", target_type="heading", target="Architecture Decisions", content="- [[<decision-note-name>]]")`

**Decision body template:**
```markdown
# Decision: <Title>

## Context
[Why this decision needed to be made]

## Options Considered
1. Option A — [[Related Pattern or Note]]
2. Option B

## Decision
[What was chosen and why]

## Consequences
- Positive: …
- Negative: …

## Related
- [[<ProjectName>-MOC]]
```

### Capture a Reusable Pattern

Patterns are **project-agnostic** — they belong to everyone on the team, not just one project.

1. Search for existing patterns: `obsidian_omnisearch("<pattern topic>")`
2. If similar pattern exists, consider enriching it instead of creating a duplicate
3. Create: `obsidian_write_note("Patterns/<PatternName>.md", content)`
4. Link back from the current project's MOC under "Implementation Notes"

### Weekly Review

1. List inbox notes: `obsidian_list_notes("Inbox")`
2. For each inbox note: read → decide (promote to typed note, append to existing, or delete)
3. Search for unlinked mentions: `obsidian_omnisearch("<project name>")` — find notes that mention
   a project but aren't linked to its MOC
4. Update any `status` frontmatter that's stale:
   `obsidian_patch_note(..., operation="replace", target_type="frontmatter", target="status", content="completed")`
5. Update `updated` timestamp on active MOCs

---

## Linking Rules

Every note must link to at least:
- Its parent project MOC (if project-scoped)
- Any existing notes on related concepts

When writing note content, use wikilinks naturally in prose:
```markdown
This decision builds on [[JWT Authentication Pattern]] from the previous API project.
```

Use placeholder links `[[Topic Not Yet Documented]]` freely — they create visible knowledge gaps
in the graph view and serve as a TODO list.

---

## Raw Ingestion (Karpathy Mode)

If the user wants to ingest external sources — articles, PDFs, GitHub repos, documentation —
into the `raw/` folder and have the LLM compile them into `wiki/`, that is a **different workflow**.

**Read `references/karpathy-ingest.md` before proceeding with any raw ingestion task.**

Triggers for this mode:
- "ingest this", "add to raw", "process this article/repo/PDF"
- "build a wiki from", "compile this into notes"
- "I want to do RAG on my vault"
- User drops files into `raw/` and asks what to do next
