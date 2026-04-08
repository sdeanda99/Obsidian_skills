# Karpathy Raw Ingest Workflow

You are switching into **compilation mode**. The user wants to ingest external source material
(articles, PDFs, GitHub repos, docs, meeting notes) and have you synthesize it into structured
wiki articles in the `wiki/` folder.

---

## Mental Model

Think of yourself as a compiler, not a note-taker:

```
raw/   →  (immutable source material — never modify these)
  ↓  LLM reads and synthesizes
wiki/  →  (your output: encyclopedia-style articles, continuously updated)
```

The human drops things in `raw/`. You compile them into `wiki/`. The human reads `wiki/`.

---

## Folder Structure

```
vault/
├── raw/
│   └── <topic>/
│       └── YYYY-MM-DD-source-name.md   ← timestamped, immutable
└── wiki/
    ├── index.md                         ← catalog of every wiki page (update every ingest)
    ├── log.md                           ← append-only operation log
    └── <topic>/
        └── <concept-name>.md           ← synthesized encyclopedia article
```

---

## Ingest Pipeline

Follow these steps in order for every ingestion request:

### Step 1 — Read `wiki/index.md`
Always start here. It tells you what already exists so you don't duplicate.
```
obsidian_read_note("wiki/index.md")
```
If `wiki/index.md` doesn't exist yet, create it (see Index format below).

### Step 2 — Read the source material
```
obsidian_read_note("raw/<topic>/<source-file>.md")
```
If the source isn't in `raw/` yet, create it there first:
```
obsidian_write_note("raw/<topic>/YYYY-MM-DD-<source-name>.md", <raw content>)
```
Raw files are **immutable** — never patch or update them after creation.

### Step 3 — Extract key concepts
From the source, identify:
- Core concepts and definitions worth their own wiki page
- Entities (tools, frameworks, people, companies) that recur
- Decisions, tradeoffs, or comparisons made in the source
- Connections to concepts already in `wiki/index.md`

### Step 4 — Resolve against existing wiki pages
For each concept extracted:
- If a wiki page already exists → **enrich it** (append new insights, update sections, add source citation)
- If no page exists → **create it** as a new encyclopedia article

Use `obsidian_read_note` to check existing pages before writing.

### Step 5 — Write or update wiki pages

**New page:**
```
obsidian_write_note("wiki/<topic>/<concept-name>.md", content)
```

**Enrich existing page:**
```
obsidian_patch_note("wiki/<topic>/<concept-name>.md",
  operation="append",
  target_type="heading",
  target="Sources",
  content="\n- [[raw/<topic>/<source-file>]] — <one-line summary>")
```

### Step 6 — Update `wiki/index.md`
Add any new pages to the index. One line per page: `[[link]] — one-line summary`.

### Step 7 — Append to `wiki/log.md`
```
obsidian_patch_note("wiki/log.md",
  operation="append",
  target_type="heading",
  target="Log",
  content="\n- YYYY-MM-DD: Ingested [[raw/<topic>/<source>]] → created/updated [[wiki/<topic>/<concept>]]")
```

---

## Wiki Article Format

Each wiki page is an encyclopedia article, not an atomic note. It should be:
- **Comprehensive** on its topic — synthesize across all sources that touch it
- **Continuously enriched** — new ingestions add to it, never replace it
- **Densely linked** — wikilink every concept, tool, or entity that has its own page

```markdown
---
type: wiki
topic: <kebab-case-topic>
sources: [raw/<topic>/<file1>.md, raw/<topic>/<file2>.md]
updated: YYYY-MM-DD
---

# <Concept Name>

## Summary
[2-4 sentence synthesis of what this is]

## Key Details
[Main body — synthesized from all sources]

## Tradeoffs / Comparisons
[If applicable]

## Related
- [[Related Concept 1]]
- [[Related Concept 2]]

## Sources
- [[raw/<topic>/<source>]] — <one-line description of what this source contributed>
```

---

## Index Format (`wiki/index.md`)

```markdown
---
type: wiki-index
updated: YYYY-MM-DD
---

# Wiki Index

## <Category>
- [[wiki/<topic>/<concept>]] — <one-line summary>

## <Category>
- [[wiki/<topic>/<concept>]] — <one-line summary>
```

Organize by category. Keep entries alphabetical within each category.
Update this file after every ingest session.

---

## Log Format (`wiki/log.md`)

```markdown
---
type: wiki-log
---

# Log

- YYYY-MM-DD: Ingested [[raw/topic/source]] → created [[wiki/topic/concept]], [[wiki/topic/concept2]]
- YYYY-MM-DD: Query — "question asked" → answered from [[wiki/topic/concept]]
- YYYY-MM-DD: Lint — fixed 3 broken links, removed 1 orphaned page
```

Append only. Never edit past entries.

---

## Query Workflow

When the user asks a question that should be answered from the wiki:

1. Read `wiki/index.md` to identify relevant pages
2. Read each relevant page with `obsidian_read_note`
3. Synthesize an answer with citations: "According to [[wiki/auth/jwt-tokens]], …"
4. Append to log: `YYYY-MM-DD: Query — "<question>" → [[wiki/page1]], [[wiki/page2]]`

---

## Key Rules

- **Never modify `raw/`** files after creation — they are the source of truth
- **Always update index.md** after any ingest
- **Always append to log.md** after any operation
- **Enrich, don't duplicate** — if a wiki page exists, add to it
- **Dense linking** — every entity/concept that has a wiki page should be wikilinked
- When done with raw ingestion, you can return to the standard atomic notes workflow
  in the main SKILL.md for any developer note-taking tasks
