---
name: obsidian-dev-notes
description: >
  Manages structured developer knowledge in Obsidian using atomic typed notes, Maps of Content
  (MOCs), and bi-directional wikilinks. Use whenever a developer needs to: start a new project
  in Obsidian, document an architectural or technical decision, capture a reusable pattern,
  record a learning or insight, run a weekly review, search for existing knowledge before
  creating new notes, or maintain a project MOC. Also triggers for: "add this to my notes",
  "document this decision", "create a project hub", "update my Obsidian", "capture this
  pattern", "link this to my project". For raw source ingestion (articles, PDFs, repos), this
  skill will ask the user which ingestion mode to use.
---

# Obsidian Developer Notes

You are managing a developer's Obsidian knowledge base. Your job is to write and maintain
structured, interconnected notes that compound in value over time. Notes are atomic, typed,
and always linked back to related concepts and project hubs.

All vault operations use `tools/obsidian.ts`. For fuzzy full-text search, use
`tools/omnisearch.ts`. This skill builds on `obsidian-cli` — read that skill for the
heading-targeted insert pattern and vault targeting details.

---

## Vault Folder Schema

```
vault/
├── Projects/       ← one MOC per project (the hub)
├── Decisions/      ← architectural and technical decisions
├── Patterns/       ← reusable solutions worth documenting
├── Learnings/      ← concepts, insights, things discovered
├── Retrospectives/ ← post-project or sprint reviews
├── Inbox/          ← longer captures, processed during weekly review
├── raw/            ← external source material (articles, PDFs, repos)
└── wiki/           ← LLM-compiled synthesis from raw/ (Karpathy ingest)
```

Route every note to its folder based on `type` frontmatter. If unsure, prefer `Learnings/`
for concepts and `Decisions/` for choices.

---

## Frontmatter Schema by Note Type

Set each field with `setProperty({ name, value, path })`.

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

Before writing any new note, always search the vault first. This prevents duplication and
reveals existing knowledge to link to.

```
1. omnisearch({ query }) — fuzzy search by topic/keywords
2. Review results:
   - Exact match found → link to it, don't duplicate
   - Related notes found → create new note but link to findings
   - Nothing found → create fresh atomic note
```

---

## Workflows

### New Project

1. Search: `omnisearch({ query: "<tech> <domain> project" })` — find related past projects
2. Create MOC: `createNote({ path: "Projects/<ProjectName>-MOC.md", template: "MOC", overwrite: false })`
   - If no MOC template exists in Obsidian, use the body template below
3. Set initial properties:
   ```
   setProperty({ name: "type", value: "moc", path: "Projects/<ProjectName>-MOC.md" })
   setProperty({ name: "project", value: "<kebab-name>", path: ... })
   setProperty({ name: "status", value: "planning", path: ... })
   setProperty({ name: "created", value: "YYYY-MM-DD", path: ... })
   setProperty({ name: "updated", value: "YYYY-MM-DD", path: ... })
   ```
4. Link to any related past projects found in step 1

**MOC body template (use if no Obsidian template configured):**
```markdown
# <Project Name> — Project MOC

## Overview
[One paragraph description]

## Key Concepts
- [[Concept 1]]

## Architecture Decisions
- [[Decision: <Topic>]]

## Implementation Notes

## Tasks
- [ ] Initial setup

## Learnings

## Retrospectives

## Related Projects
- [[<Past Project>-MOC]]
```

### Document a Decision

1. Search: `omnisearch({ query: "<decision topic>" })` — find existing decisions
2. Create: `createNote({ path: "Decisions/<ProjectName>-<Decision>.md", template: "Decision" })`
3. Link decision into MOC (heading-targeted insert pattern):
   ```
   { output } = readNote({ path: "Projects/<ProjectName>-MOC.md" })
   // Find "## Architecture Decisions" in output, insert "- [[<decision-note-name>]]" below it
   createNote({ path: "Projects/<ProjectName>-MOC.md", content: modified, overwrite: true })
   ```
4. Update MOC `updated` property: `setProperty({ name: "updated", value: "YYYY-MM-DD", path: ... })`

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

Patterns are project-agnostic — they belong to any future project, not just the current one.

1. Search: `omnisearch({ query: "<pattern topic>" })` — find similar patterns first
2. If similar exists, enrich it instead of creating a duplicate
3. Create: `createNote({ path: "Patterns/<PatternName>.md", template: "Pattern" })`
4. Link into current project MOC under `## Implementation Notes` (heading-targeted insert)

### Weekly Review

1. `listFiles({ folder: "Inbox" })` — list inbox notes
2. For each: `readNote({ file })` → decide: promote to typed note, append to existing, or delete
3. `readDailyNote()` — retrieve this week's daily captures → promote or discard each
4. `getOrphans()` — find notes with no incoming links → connect to a MOC or add to Inbox
5. Check active project health: `listTasks({ file: "Projects/<Project>-MOC.md", todo: true })`
6. Update stale MOCs: `setProperty({ name: "updated", value: "YYYY-MM-DD", file: "<MOC>" })`
7. Before archiving a project:
   ```
   getBacklinks({ path: "Projects/<ProjectName>-MOC.md" })  → confirm it's well-linked
   setProperty({ name: "status", value: "archived", path: ... })
   ```

### Task-Driven Project Tracking

Every MOC has a `## Tasks` section. Track work without switching tools.

```
# Surface open work
listTasks({ file: "Projects/X-MOC.md", todo: true })

# Get line numbers to toggle tasks
listTasks({ file: "Projects/X-MOC.md", verbose: true })

# Mark a task done
toggleTask({ file: "Projects/X-MOC.md", line: N, done: true })

# Completion audit at project close
listTasks({ file: "Projects/X-MOC.md", done: true })
```

### Daily Capture

Quick insights go to the daily note, not the Inbox. Use Inbox for longer captures that need
their own note file.

```
appendToDailyNote({ content: "- Realized X pattern while implementing Y" })
appendToDailyNote({ content: "- [ ] Follow up on Z decision" })
```

Process daily captures during weekly review via `readDailyNote()`.

### Template-Based Note Creation

If Obsidian's Templates or Templater plugin is configured, use templates to pre-fill
frontmatter and body structure:

```
createNote({ name: "<ProjectName>-Auth-Decision", template: "Decision" })
```

Expected template names: `MOC`, `Decision`, `Pattern`, `Learning`, `Retrospective`.
Store templates in your vault's `Templates/` folder.

If templates are not configured, use the inline body templates documented in each workflow
above — they produce identical structure.

---

## Linking Rules

Every note must link to at least:
- Its parent project MOC (if project-scoped)
- Any existing notes on related concepts found during the Search Before Creating step

Write wikilinks naturally in prose:
```markdown
This decision builds on [[JWT Authentication Pattern]] from the previous API project.
```

Use placeholder links `[[Topic Not Yet Documented]]` freely — they create visible knowledge
gaps in graph view and serve as a TODO list.

---

## Raw Ingestion — User-Verified Routing

When the user mentions ingesting external sources (articles, PDFs, GitHub repos,
documentation), **do not auto-route**. Ask:

> "I can handle this two ways:
> - **Karpathy mode** — ingest the source into `raw/`, then synthesize it into `wiki/`
>   articles (best for large sources you'll query repeatedly as a knowledge base)
> - **Direct typed notes** — read the source now and create Learnings/Patterns/Decisions
>   from it immediately (best for one-off sources or when you know what to extract)
>
> Which do you prefer?"

- **Karpathy mode** → read `references/karpathy-ingest.md` and follow that workflow exactly
- **Direct typed notes** → follow the normal Note Creation workflows above

Triggers for this prompt: "ingest", "add to raw", "process this article/repo/PDF",
"build a wiki from", "compile into notes", "RAG on my vault", user drops files into `raw/`.
