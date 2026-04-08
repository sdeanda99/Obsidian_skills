# Obsidian CLI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the REST API skill with a native Obsidian CLI skill and typed TypeScript tool, fully redesign the dev-notes skill to use CLI features, and keep Omnisearch unchanged.

**Architecture:** A two-layer skill architecture — `obsidian-cli` as a general vault management API layer, `obsidian-dev-notes` as a developer knowledge domain layer on top. A new `tools/obsidian.ts` wraps the `obsidian` CLI binary via `Bun.$` and exports 16 typed tools. The existing `tools/omnisearch.ts` is untouched.

**Tech Stack:** TypeScript, Bun runtime, `@opencode-ai/plugin`, Obsidian CLI 1.12+, Markdown skill files.

**Spec:** `.opencode/plans/2026-04-07-obsidian-cli-redesign.md`

---

## Chunk 1: Housekeeping

**Files:**
- Move: `obsidian-rest-api/` → `docs/archive/obsidian-rest-api/`
- Create dirs: `obsidian-cli/references/`, `docs/superpowers/`

---

- [ ] **Step 1: Create archive directory and move REST API skill**

```bash
mkdir -p docs/archive
mv obsidian-rest-api docs/archive/obsidian-rest-api
```

Verify:
```bash
ls docs/archive/obsidian-rest-api/
# Expected: SKILL.md  references/
```

- [ ] **Step 2: Create new skill directory structure**

```bash
mkdir -p obsidian-cli/references
ls obsidian-cli/
# Expected: references/
```

- [ ] **Step 3: Commit housekeeping**

```bash
git add -A
git commit -m "chore: archive obsidian-rest-api, scaffold obsidian-cli directory"
```

---

## Chunk 2: `tools/obsidian.ts`

**Files:**
- Create: `tools/obsidian.ts`

This is the only executable code in the project. All 16 exports follow the same pattern: `buildArgs` assembles the CLI command array, `Bun.$\`${args}\`` runs it, errors are caught and returned as JSON.

---

- [ ] **Step 1: Create `tools/obsidian.ts` with full implementation**

```typescript
import { tool } from "@opencode-ai/plugin"

// --- Interfaces ---

interface ObsidianTag {
  name: string
  count?: number
}

interface ObsidianTask {
  path?: string
  line?: number
  content: string
  status: string
}

interface ObsidianBacklink {
  path: string
  count?: number
}

interface ObsidianProperty {
  name: string
  value: unknown
  type?: string
}

// --- Helpers ---

function buildArgs(
  vault: string | undefined,
  command: string,
  params: Record<string, string | boolean | number | undefined>
): string[] {
  const args: string[] = ["obsidian"]
  if (vault) args.push(`vault=${vault}`)
  args.push(command)
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === false) continue
    if (val === true) {
      args.push(key)
    } else {
      const encoded = String(val).replace(/\n/g, "\\n").replace(/\t/g, "\\t")
      args.push(`${key}=${encoded}`)
    }
  }
  return args
}

function handleError(error: unknown): string {
  const err = error as Error
  if (err.message.includes("command not found") || err.message.includes("not found")) {
    return JSON.stringify({
      error: "Obsidian CLI not found",
      details: "Enable CLI in Obsidian: Settings → General → Command line interface. Restart your terminal after registration.",
    }, null, 2)
  }
  if (
    err.message.includes("No vault") ||
    err.message.includes("Cannot connect") ||
    err.message.includes("ECONNREFUSED")
  ) {
    return JSON.stringify({
      error: "Cannot connect to Obsidian",
      details: "Open Obsidian and ensure a vault is active, or pass vault=<name> to target a specific vault.",
    }, null, 2)
  }
  return JSON.stringify({ error: "CLI command failed", message: err.message }, null, 2)
}

async function run(args: string[]): Promise<string> {
  return (await Bun.$`${args}`.text()).trim()
}

// --- Note Tools ---

export const createNote = tool({
  description: "Create or overwrite a note in the Obsidian vault. Provide name (wikilink-style) or path (full vault path). Use appendToNote for adding to existing notes. Set overwrite: true to replace existing content.",
  args: {
    name: tool.schema.string().optional().describe("File name without path or extension"),
    path: tool.schema.string().optional().describe("Full path from vault root, e.g. Projects/MyMOC.md"),
    content: tool.schema.string().optional().describe("Note content. Actual newlines are encoded automatically."),
    template: tool.schema.string().optional().describe("Obsidian template name to apply (requires Templates plugin)"),
    overwrite: tool.schema.boolean().default(false).describe("Overwrite existing file. Default: false"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, path, content, template, overwrite, vault } = args
    try {
      const output = await run(buildArgs(vault, "create", { name, path, content, template, overwrite }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const readNote = tool({
  description: "Read the full markdown content of a note. Use before modifying a note (read-modify-overwrite pattern for heading-targeted inserts). Defaults to the active file.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "read", { file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const appendToNote = tool({
  description: "Append content to the end of a note. For inserting under a specific heading, use the read-modify-overwrite pattern with readNote + createNote instead.",
  args: {
    content: tool.schema.string().describe("Content to append. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    inline: tool.schema.boolean().optional().describe("Append without prepending a newline"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { content, file, path, inline, vault } = args
    try {
      const output = await run(buildArgs(vault, "append", { content, file, path, inline }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const deleteNote = tool({
  description: "Delete a note. Moves to system trash by default. Pass permanent: true to skip trash.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    permanent: tool.schema.boolean().optional().describe("Skip trash, delete permanently"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, permanent, vault } = args
    try {
      const output = await run(buildArgs(vault, "delete", { file, path, permanent }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Files & Folders ---

export const listFiles = tool({
  description: "List notes in the vault or a specific folder. Returns file paths. Use to browse vault structure or find notes in a folder (e.g. listFiles({ folder: 'Inbox' })).",
  args: {
    folder: tool.schema.string().optional().describe("Folder path relative to vault root. Omit to list all files."),
    ext: tool.schema.string().optional().describe("Filter by extension, e.g. 'md'"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { folder, ext, vault } = args
    try {
      const output = await run(buildArgs(vault, "files", { folder, ext }))
      const files = output.split("\n").filter(Boolean)
      return JSON.stringify({ files }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Properties ---

export const setProperty = tool({
  description: "Set a frontmatter property on a note. Use to update fields like status, updated date, or tags. Specify type for new properties (defaults to text if omitted).",
  args: {
    name: tool.schema.string().describe("Property name (frontmatter key). Required."),
    value: tool.schema.string().describe("Property value. Required."),
    type: tool.schema.string().optional().describe("Property type: text | list | number | checkbox | date | datetime"),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, value, type, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:set", { name, value, type, file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const readProperty = tool({
  description: "Read the value of a single frontmatter property from a note.",
  args: {
    name: tool.schema.string().describe("Property name. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:read", { name, file, path }))
      return JSON.stringify({ name, value: output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const removeProperty = tool({
  description: "Remove a frontmatter property from a note.",
  args: {
    name: tool.schema.string().describe("Property name to remove. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:remove", { name, file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const listProperties = tool({
  description: "List all frontmatter properties on a note. Returns property names, values, and types.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "properties", { file, path, format: "json" }))
      const properties: ObsidianProperty[] = JSON.parse(output)
      return JSON.stringify({ properties }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Tags ---

export const listTags = tool({
  description: "List tags in the vault or on a specific note. Returns tag names and optional counts. Use for vault-wide tag queries or to inspect a note's tags.",
  args: {
    file: tool.schema.string().optional().describe("File name. Omit to query vault-wide."),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    sort: tool.schema.string().optional().describe("Sort by 'count' (frequency) or omit for alphabetical"),
    counts: tool.schema.boolean().optional().describe("Include occurrence counts in results"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, sort, counts, vault } = args
    try {
      const output = await run(buildArgs(vault, "tags", { file, path, sort, counts, format: "json" }))
      const tags: ObsidianTag[] = JSON.parse(output)
      return JSON.stringify({ tags }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Tasks ---

export const listTasks = tool({
  description: "List tasks in a file or across the vault. Filter by status. Use verbose for file paths and line numbers. Use for project health checks and weekly reviews.",
  args: {
    file: tool.schema.string().optional().describe("File name. Omit to query vault-wide."),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    done: tool.schema.boolean().optional().describe("Show only completed tasks"),
    todo: tool.schema.boolean().optional().describe("Show only incomplete tasks"),
    verbose: tool.schema.boolean().optional().describe("Group by file with line numbers (needed for toggleTask)"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, done, todo, verbose, vault } = args
    try {
      const output = await run(buildArgs(vault, "tasks", { file, path, done, todo, verbose, format: "json" }))
      const tasks: ObsidianTask[] = JSON.parse(output)
      return JSON.stringify({ tasks }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const toggleTask = tool({
  description: "Toggle or set the completion status of a specific task by file and line number. Use listTasks with verbose: true first to find line numbers.",
  args: {
    line: tool.schema.number().int().positive().describe("Line number of the task. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    done: tool.schema.boolean().optional().describe("Mark as done [x]"),
    todo: tool.schema.boolean().optional().describe("Mark as todo [ ]"),
    toggle: tool.schema.boolean().optional().describe("Toggle current status"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { line, file, path, done, todo, toggle, vault } = args
    try {
      const output = await run(buildArgs(vault, "task", { line, file, path, done, todo, toggle }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Links ---

export const getBacklinks = tool({
  description: "List files that link to a given note. Use during weekly review to verify a note is well-connected, or before archiving a project to confirm the MOC is reachable.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "backlinks", { file, path, format: "json" }))
      const backlinks: ObsidianBacklink[] = JSON.parse(output)
      return JSON.stringify({ backlinks }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const getOrphans = tool({
  description: "List notes with no incoming links. Use during weekly review to find disconnected notes that need to be connected to a MOC or processed from Inbox.",
  args: {
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { vault } = args
    try {
      const output = await run(buildArgs(vault, "orphans", {}))
      const orphans = output.split("\n").filter(Boolean)
      return JSON.stringify({ orphans }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Daily Notes ---

export const readDailyNote = tool({
  description: "Read today's daily note content. Use during weekly review to retrieve daily captures for processing into typed notes.",
  args: {
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { vault } = args
    try {
      const output = await run(buildArgs(vault, "daily:read", {}))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const appendToDailyNote = tool({
  description: "Append content to today's daily note. Use for quick captures — insights, tasks, ideas — to be processed into typed notes during weekly review.",
  args: {
    content: tool.schema.string().describe("Content to append. Required."),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { content, vault } = args
    try {
      const output = await run(buildArgs(vault, "daily:append", { content }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Escape Hatch ---

export const evalJs = tool({
  description: "Run JavaScript in the Obsidian app context. Advanced escape hatch — use only when no other tool covers the need. Has full access to app.vault, app.metadataCache, etc. No sandbox or timeout applied. Returns raw eval output.",
  args: {
    code: tool.schema.string().describe("JavaScript to execute. Has access to the global `app` object. Required."),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { code, vault } = args
    try {
      const output = await run(buildArgs(vault, "eval", { code }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})
```

- [ ] **Step 2: Type-check the tool**

```bash
bun check tools/obsidian.ts
```

Expected: no errors. If type errors appear, fix them before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tools/obsidian.ts
git commit -m "feat: add tools/obsidian.ts CLI wrapper with 16 typed exports"
```

---

## Chunk 3: `obsidian-cli/` Skill

**Files:**
- Create: `obsidian-cli/SKILL.md`
- Create: `obsidian-cli/references/cli_reference.md`
- Create: `obsidian-cli/references/setup.md`

---

- [ ] **Step 1: Create `obsidian-cli/SKILL.md`**

```markdown
---
name: obsidian-cli
description: >
  General-purpose Obsidian vault management via the Obsidian CLI. Use when you need to
  create, read, update, or delete notes; manage frontmatter properties; query tasks or tags;
  discover backlinks or orphaned notes; or interact with daily notes and templates. Requires
  Obsidian 1.12+ with CLI enabled (Settings → General → Command line interface) and Obsidian
  running. For fuzzy full-text search, use the omnisearch tool instead.
---

# Obsidian CLI

## Overview

The Obsidian CLI is a first-party command line interface built into Obsidian 1.12+. It provides
native vault access without requiring a community plugin or API key. The CLI connects to the
running Obsidian app — **Obsidian must be running** for any command to work.

This skill replaces the previous `obsidian-rest-api` approach. Reference docs for the old REST
API are preserved in `docs/archive/obsidian-rest-api/`.

## Prerequisites

1. Obsidian installer 1.12.7 or later — check via Help → About → Installer version
2. CLI enabled: Settings → General → Command line interface → toggle on → follow prompts
3. Restart terminal after registration
4. Verify: `obsidian version` (should print a version number)

See `references/setup.md` for platform-specific setup (Linux, macOS, Windows).

## Available Tools

All vault operations go through `tools/obsidian.ts`. For fuzzy full-text search with scores
and excerpts, use `tools/omnisearch.ts` instead.

| Tool | Purpose |
|---|---|
| `createNote` | Create or overwrite a note |
| `readNote` | Read full note content |
| `appendToNote` | Append content to end of note |
| `deleteNote` | Delete a note (trash by default) |
| `listFiles` | List notes in a folder |
| `setProperty` | Set a frontmatter property |
| `readProperty` | Read one frontmatter property |
| `removeProperty` | Remove a frontmatter property |
| `listProperties` | List all properties on a note |
| `listTags` | List tags (file-scoped or vault-wide) |
| `listTasks` | List tasks (file-scoped or vault-wide) |
| `toggleTask` | Toggle or set a task's completion status |
| `getBacklinks` | List files that link to a note |
| `getOrphans` | List files with no incoming links |
| `readDailyNote` | Read today's daily note |
| `appendToDailyNote` | Append to today's daily note |
| `evalJs` | Run JavaScript in Obsidian app context (advanced) |

## Heading-Targeted Insert Pattern

The CLI does not support surgical heading-targeted inserts. Use this named pattern instead:

```
1. { output } = readNote({ file: "MyNote" })
2. Find the target heading in output (e.g. "## Architecture Decisions")
3. Splice new content immediately after that heading line
4. createNote({ file: "MyNote", content: modifiedOutput, overwrite: true })
```

Document this pattern in any skill that builds on `obsidian-cli` — it is the standard
replacement for the REST API's `PATCH` with `Target-Type: heading`.

## Vault & File Targeting

- **Default vault:** The active Obsidian vault, or the vault whose folder matches your working directory.
- **Specify vault:** Pass `vault="My Vault"` to any tool.
- **`file` parameter:** Wikilink-style resolution — no path, no extension needed. Best for unambiguous filenames.
- **`path` parameter:** Full path from vault root, e.g. `Projects/MyProject-MOC.md`. Required when filenames are ambiguous.
- `path` takes precedence over `file` when both are provided.

## When Not to Use

- **Fuzzy full-text search with scores/excerpts** → use `omnisearch` tool (port 51361)
- **REST API reference** → see `docs/archive/obsidian-rest-api/` (archived, not active)

## Reference

- `references/cli_reference.md` — condensed command reference by category
- `references/setup.md` — platform-specific installation and verification
```

- [ ] **Step 2: Create `obsidian-cli/references/cli_reference.md`**

```markdown
# CLI Command Reference

Condensed reference for Obsidian CLI commands used in vault operations. For the full CLI
documentation, run `obsidian help` or see https://obsidian.md/help/cli.

## File Operations

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian create` | `name`, `path`, `content`, `template`, `overwrite` | Dirs created automatically |
| `obsidian read` | `file`, `path` | Defaults to active file |
| `obsidian append` | `content` (required), `file`, `path`, `inline` | `inline` skips leading newline |
| `obsidian prepend` | `content` (required), `file`, `path` | Inserts after frontmatter |
| `obsidian delete` | `file`, `path`, `permanent` | Trash by default |
| `obsidian move` | `to` (required), `file`, `path` | Updates wikilinks automatically |
| `obsidian rename` | `name` (required), `file`, `path` | Extension preserved if omitted |
| `obsidian files` | `folder`, `ext`, `total` | Lists all matching files |
| `obsidian file` | `file`, `path` | Shows file metadata |

## Properties (Frontmatter)

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian property:set` | `name`, `value`, `type`, `file`, `path` | Types: text\|list\|number\|checkbox\|date\|datetime |
| `obsidian property:read` | `name`, `file`, `path` | Returns raw value |
| `obsidian property:remove` | `name`, `file`, `path` | Removes field entirely |
| `obsidian properties` | `file`, `path`, `format` | `format=json` for structured output |

## Tags

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian tags` | `file`, `path`, `sort`, `counts`, `format` | `format=json\|tsv\|csv` |
| `obsidian tag` | `name` (required), `total`, `verbose` | Info on a specific tag |

## Tasks

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian tasks` | `file`, `path`, `done`, `todo`, `verbose`, `format` | `verbose` adds line numbers |
| `obsidian task` | `file`, `path`, `line`, `done`, `todo`, `toggle` | Line number required |

## Links

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian backlinks` | `file`, `path`, `format` | Files that link to target |
| `obsidian orphans` | (none) | Files with no incoming links |
| `obsidian unresolved` | `verbose`, `format` | Broken wikilinks |

## Daily Notes

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian daily` | `paneType` | Opens today's note |
| `obsidian daily:read` | (none) | Returns content |
| `obsidian daily:append` | `content` (required), `open` | Appends to today |
| `obsidian daily:prepend` | `content` (required), `open` | Prepends to today |
| `obsidian daily:path` | (none) | Returns file path |

## Escape Hatch

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian eval` | `code` (required) | Full access to `app` object |

## Parameter Notes

- `file=<name>` — wikilink-style resolution (no path, no extension)
- `path=<path>` — full path from vault root, e.g. `Projects/Note.md`
- `vault=<name>` — must be first parameter before the command
- Content with spaces: wrap in quotes — `content="Hello world"`
- Newlines in content: use `\n` — `content="Line 1\nLine 2"`
- `format=json` — use wherever available for structured output
```

- [ ] **Step 3: Create `obsidian-cli/references/setup.md`**

```markdown
# Obsidian CLI Setup

## Requirements

- Obsidian installer version **1.12.7 or later**
- To check: Obsidian → Help → About → look for "Installer version"
- If older: download the latest installer from https://obsidian.md

## Enable the CLI

1. Open Obsidian
2. Go to **Settings** → **General**
3. Toggle on **Command line interface**
4. Follow the prompt to register the CLI (adds `obsidian` to your system PATH)
5. **Restart your terminal** — PATH changes only take effect in new sessions

## Verify Installation

```bash
obsidian version
# Expected output: a version number, e.g. 1.12.7
```

## Platform Notes

### Linux

The CLI binary is copied to `~/.local/bin/obsidian`. Ensure this is in your PATH:

```bash
# Check
echo $PATH | grep -q "$HOME/.local/bin" && echo "OK" || echo "Missing"

# Add to PATH if missing — add this line to ~/.bashrc or ~/.zshrc:
export PATH="$PATH:$HOME/.local/bin"
```

### macOS

A symlink is created at `/usr/local/bin/obsidian`. Requires admin privileges (a system dialog appears during registration).

```bash
# Verify symlink
ls -l /usr/local/bin/obsidian

# If missing, create manually:
sudo ln -sf /Applications/Obsidian.app/Contents/MacOS/obsidian-cli /usr/local/bin/obsidian
```

### Windows

The Obsidian installer directory is added to your user PATH. Restart the terminal after registration. Requires Obsidian 1.12.7+ installer.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `obsidian: command not found` | Restart terminal; check PATH for your platform |
| `No vault` error | Open Obsidian and ensure a vault is active |
| Commands hang | Obsidian app may not be running — launch it first |
| Old PATH entry in `~/.zprofile` | Delete lines starting with `# Added by Obsidian` (replaced by new registration) |
```

- [ ] **Step 4: Commit**

```bash
git add obsidian-cli/
git commit -m "feat: add obsidian-cli skill with CLI reference and setup docs"
```

---

## Chunk 4: `obsidian-dev-notes/SKILL.md` Redesign

**Files:**
- Rewrite: `obsidian-dev-notes/SKILL.md` (full replacement)
- Keep unchanged: `obsidian-dev-notes/references/karpathy-ingest.md`

---

- [ ] **Step 1: Replace `obsidian-dev-notes/SKILL.md` with full redesign**

```markdown
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
```

- [ ] **Step 2: Verify karpathy-ingest.md is untouched**

```bash
ls obsidian-dev-notes/references/karpathy-ingest.md
# Expected: file path printed (confirms file exists)

git diff obsidian-dev-notes/references/karpathy-ingest.md
# Expected: no output (no changes)
```

- [ ] **Step 3: Commit**

```bash
git add obsidian-dev-notes/SKILL.md
git commit -m "feat: redesign obsidian-dev-notes skill for CLI tools and new workflows"
```

---

## Chunk 5: Docs, AGENTS.md, README.md, and Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`

---

- [ ] **Step 1: Update `AGENTS.md`**

Replace the full content with:

```markdown
# AGENTS.md — Coding Agent Reference

This repository provides **OpenCode skills and tools** for Obsidian integration. It is a
documentation-first project with two TypeScript tool files and Markdown skill definitions
consumed by OpenCode agents.

---

## Repository Structure

```
obsidian-cli/         # Skill: general-purpose vault management via Obsidian CLI
  SKILL.md            # Triggers: create/read/update/delete notes, properties, tasks, tags
  references/         # cli_reference.md, setup.md

obsidian-dev-notes/   # Skill: structured developer knowledge (builds on obsidian-cli)
  SKILL.md            # Triggers: MOCs, decisions, patterns, learnings, weekly review
  references/         # karpathy-ingest.md

tools/
  omnisearch.ts       # OpenCode tool: fuzzy search via Omnisearch HTTP API (port 51361)
  obsidian.ts         # OpenCode tool: vault CRUD via Obsidian CLI (16 exports)

docs/
  archive/
    obsidian-rest-api/  # Archived REST API skill (no longer active)
  superpowers/          # Design specs and implementation plans
```

---

## Build & Install Commands

```bash
uv pip install -e .             # Install Python deps (preferred)
pip install -r requirements.txt # Alternative

# Deploy skills to OpenCode
cp -r obsidian-cli ~/.claude/skills/
cp -r obsidian-dev-notes ~/.claude/skills/
cp tools/omnisearch.ts ~/.claude/tools/
cp tools/obsidian.ts ~/.claude/tools/

# Type-check tools
bun check tools/omnisearch.ts
bun check tools/obsidian.ts

# Run a tool directly
bun run tools/obsidian.ts
```

---

## Testing

No test suite configured. If added:

```bash
pytest tests/                          # All Python tests
pytest tests/test_foo.py::test_bar -v  # Single Python test
bun test                               # TypeScript tests (Bun built-in)
bun test tools/obsidian.test.ts        # Single TypeScript test file
```

---

## TypeScript Tool Conventions (`tools/*.ts`)

Both `tools/omnisearch.ts` and `tools/obsidian.ts` are canonical examples.

### Imports & Structure

```typescript
import { tool } from "@opencode-ai/plugin"   // only required import

interface MyResult { ... }   // PascalCase interfaces, after imports

export const myTool = tool({
  description: "Verb phrase. State WHEN to use this tool explicitly.",
  args: {
    query: tool.schema.string().describe("..."),
    limit: tool.schema.number().int().positive().default(10).describe("..."),
  },
  async execute(args) {
    const { query, limit } = args
    return JSON.stringify(result, null, 2)   // always return JSON string
  },
})
```

### CLI Wrapper Pattern (`tools/obsidian.ts`)

For tools that wrap shell commands via `Bun.$`:

```typescript
async function run(args: string[]): Promise<string> {
  return (await Bun.$`${args}`.text()).trim()
}

// Build args as an array — Bun Shell handles quoting/escaping
function buildArgs(vault, command, params) {
  const args = ["obsidian"]
  if (vault) args.push(`vault=${vault}`)
  args.push(command)
  // encode newlines/tabs for CLI content params
  for (const [key, val] of Object.entries(params)) {
    if (val === true) args.push(key)
    else if (val) args.push(`${key}=${String(val).replace(/\n/g, "\\n")}`)
  }
  return args
}
```

### Error Handling

All errors are **returned as JSON — never thrown**.

```typescript
try {
  const result = await fetch(url)
  if (!result.ok) return JSON.stringify({ error: "...", status: result.status }, null, 2)
  return JSON.stringify(await result.json(), null, 2)
} catch (error) {
  const err = error as Error
  return JSON.stringify({ error: "...", details: "...", originalError: err.message }, null, 2)
}
```

- Check `response.ok` before parsing body (HTTP tools)
- Include `details` for user-fixable failures
- Cast errors as `const err = error as Error` — never use `any`

### Formatting

- 2-space indentation; no semicolons
- `const`/`let` only — never `var`
- `async/await` over `.then()` chains
- `Bun.$\`command\`` for shell operations (not `child_process`)

---

## Skill File Conventions (`*/SKILL.md`)

### Frontmatter

```yaml
---
name: skill-name-kebab-case   # must match directory name
description: >
  Verb phrase. Explicitly state WHEN to use this skill (triggers) and what it enables.
---
```

Bad description: `"Helps with Obsidian."` — too vague, won't trigger correctly.
Good description: explicit triggers ("Use when you need to create notes...") with specifics.

### Content Structure

```markdown
## Overview        — one-paragraph summary
## Prerequisites   — what must be set up (if any)
## Available Tools — table of tool exports with one-line descriptions
## Workflows       — numbered steps; reference tool calls in backticks
## Reference       — links to references/ files
```

### Reference Files (`references/*.md`)

Use fenced code blocks with language tags. Include concrete examples (tool calls, content templates).

---

## Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| TypeScript tool exports | `camelCase` | `createNote`, `listTasks` |
| TypeScript interfaces | `PascalCase` | `ObsidianTask`, `SearchResult` |
| Skill directories | `kebab-case` | `obsidian-cli/` |
| Skill files | `SKILL.md` (uppercase) | `obsidian-dev-notes/SKILL.md` |
| Reference docs | `snake_case.md` | `cli_reference.md` |
| Env vars | `snake_case` | `obsidian_api_keys` |

---

## Environment & Configuration

```bash
cp .env.example .env   # omnisearch only — no env vars needed for CLI
# obsidian_api_keys=<only needed if using archived REST API>
```

Default ports: Omnisearch HTTP API → `51361`. Obsidian CLI uses no port (IPC).

---

## Contributing

1. Match the style of the file you are editing — do not reformat unrelated lines.
2. Update documentation when adding or changing a tool or skill.
3. Skills must have trigger-specific `description` in YAML frontmatter.
4. Tools must handle all errors as JSON return values, never as thrown exceptions.
5. New tools → `tools/`; new skills → top-level `kebab-case/` dir with `SKILL.md` + `references/`.
6. Do not add runtime dependencies without updating `pyproject.toml` and `requirements.txt`.
7. Archived content lives in `docs/archive/` — do not delete, reference it from AGENTS.md.
```

- [ ] **Step 2: Replace `README.md` with the following content verbatim**

```markdown
# Obsidian Skills for OpenCode

OpenCode skills and tools for seamless Obsidian integration. This repository provides AI
agents with the ability to interact with your Obsidian vault through the native CLI and
search capabilities.

## Features

- **Obsidian CLI Skill** — General-purpose vault management via the native Obsidian CLI
- **Obsidian Dev Notes Skill** — Structured developer knowledge with MOCs, decisions, patterns
- **Omnisearch Custom Tool** — Fast, fuzzy vault search with result excerpts
- **Obsidian CLI Tool** — Typed TypeScript wrapper for vault CRUD, properties, tasks, and links

## Prerequisites

### Required Software

- **Obsidian** (desktop app, installer version **1.12.7 or later**)
- **Bun** (for running TypeScript tools)
- **Python** 3.10+ (for package install)

### Required Setup

1. **Obsidian CLI** — Enable in Obsidian: Settings → General → Command line interface → toggle on.
   Restart your terminal after registration. Verify with `obsidian version`.

2. **Omnisearch plugin** — Install from Community Plugins. Enable HTTP Server in Omnisearch
   settings (runs on port 51361).

See `obsidian-cli/references/setup.md` for platform-specific CLI setup (Linux, macOS, Windows).

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sdeanda99/Obsidian_skills.git
cd Obsidian_skills
```

### 2. Install Python Dependencies

**Option A: Using `uv` (recommended)**

```bash
uv pip install -e .
```

**Option B: Using standard `pip`**

```bash
pip install -r requirements.txt
```

### 3. Deploy Skills and Tools

Copy skills and tools to your OpenCode configuration:

```bash
# Skills
cp -r obsidian-cli ~/.claude/skills/
cp -r obsidian-dev-notes ~/.claude/skills/

# Tools
cp tools/omnisearch.ts ~/.claude/tools/
cp tools/obsidian.ts ~/.claude/tools/
```

Restart OpenCode to load the new skills and tools.

## Quick Start

### Using the Obsidian CLI Skill

The skill loads when you mention vault operations:

```
"Create a new note called 'Meeting Notes' with today's date"
"Update the status property on my Project MOC"
"List all tasks in my Projects folder"
"Find orphaned notes in my vault"
```

### Using the Dev Notes Skill

Structured knowledge management triggers:

```
"Start a new project hub for my authentication refactor"
"Document the decision to use JWT tokens"
"Capture the retry pattern I just implemented"
"Run my weekly review"
```

### Using the Omnisearch Tool

Search your vault for specific content:

```
"Search my vault for 'machine learning' notes"
"Find all notes mentioning 'project deadline'"
```

Test the Omnisearch endpoint directly:

```bash
curl "http://localhost:51361/search?q=test"
```

## Available Tools & Skills

### 1. Obsidian CLI Skill

**Location:** `obsidian-cli/`

**Capabilities:**
- Create, read, append, delete notes
- Manage frontmatter properties (set, read, remove, list)
- Query tasks and toggle completion
- List tags vault-wide or per-note
- Find backlinks and orphaned notes
- Interact with daily notes
- Run arbitrary JavaScript in Obsidian context (eval escape hatch)

**Documentation:**
- `obsidian-cli/SKILL.md` — Main skill guide and heading-insert pattern
- `obsidian-cli/references/cli_reference.md` — Condensed command reference
- `obsidian-cli/references/setup.md` — Platform-specific setup

### 2. Obsidian Developer Notes Skill

**Location:** `obsidian-dev-notes/`

**Capabilities:**
- Create and maintain project MOCs (Maps of Content)
- Document architectural decisions with context and trade-offs
- Capture reusable patterns linked to projects
- Record learnings and insights with typed frontmatter
- Weekly review workflow with orphan detection and daily note processing
- Task-driven project tracking per MOC
- Raw source ingestion (Karpathy mode or direct typed notes)

**Documentation:**
- `obsidian-dev-notes/SKILL.md` — Full workflow guide
- `obsidian-dev-notes/references/karpathy-ingest.md` — Raw ingestion workflow

### 3. Obsidian CLI Tool

**Location:** `tools/obsidian.ts`

**Exports (16):** `createNote`, `readNote`, `appendToNote`, `deleteNote`, `listFiles`,
`setProperty`, `readProperty`, `removeProperty`, `listProperties`, `listTags`,
`listTasks`, `toggleTask`, `getBacklinks`, `getOrphans`, `readDailyNote`,
`appendToDailyNote`, `evalJs`

### 4. Omnisearch Custom Tool

**Location:** `tools/omnisearch.ts`

**Capabilities:**
- Full-text fuzzy search across your vault
- Returns scored results with excerpts and found words
- Configurable result limits

**Documentation:**
- `docs/OMNISEARCH_TOOL.md` — Comprehensive tool guide
- `docs/omnisearch.md` — Quick reference

## Configuration

### Default Service Ports

- **Obsidian CLI:** No port — communicates directly with the running Obsidian app
- **Omnisearch HTTP API:** `http://localhost:51361`

No API keys or `.env` file required for CLI operations.

## Troubleshooting

### Obsidian CLI Not Found

```bash
obsidian version
# If "command not found":
```

1. Verify Obsidian CLI is enabled: Settings → General → Command line interface
2. Restart your terminal (PATH changes require a new session)
3. See `obsidian-cli/references/setup.md` for platform-specific fixes

### Obsidian CLI Not Responding

- Ensure Obsidian is running (the CLI requires the app to be open)
- Try `obsidian version` — if it hangs, restart Obsidian

### Omnisearch Not Finding Results

1. Check HTTP server is enabled: Obsidian → Settings → Omnisearch → Enable HTTP Server
2. Try searching in Obsidian UI first (confirms the plugin is working)
3. Test the endpoint:
   ```bash
   curl "http://localhost:51361/search?q=test"
   ```

## Documentation

Additional documentation:

- `docs/` — General documentation and guides
- `obsidian-cli/references/` — CLI command reference and setup
- `docs/archive/obsidian-rest-api/` — Archived REST API skill (reference only)
- `docs/superpowers/` — Design specs and implementation plans

## Contributing

Contributions are welcome! Please ensure:

1. Code follows existing style conventions
2. Documentation is updated for new features
3. Skills include clear "when to use" descriptions in frontmatter
4. Tools have comprehensive error handling (all errors returned as JSON, never thrown)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Obsidian](https://obsidian.md/) — The knowledge base application
- [Obsidian CLI](https://obsidian.md/help/cli) — Native CLI (Obsidian 1.12+)
- [Omnisearch Plugin](https://github.com/scambier/obsidian-omnisearch) — Search capabilities

## Version

**Current Version:** 2.0.0

---

**Author:** Sebastian De Anda
**Repository:** https://github.com/sdeanda99/Obsidian_skills
```

- [ ] **Step 3: Run final type check**

```bash
bun check tools/obsidian.ts && bun check tools/omnisearch.ts
```

Expected: no errors on either file.

- [ ] **Step 4: Final commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: update AGENTS.md and README for CLI redesign"
```

- [ ] **Step 5: Verify complete repo structure**

```bash
ls obsidian-cli/ obsidian-dev-notes/ tools/ docs/archive/
# Expected:
# obsidian-cli/: SKILL.md  references/
# obsidian-dev-notes/: SKILL.md  references/
# tools/: obsidian.ts  omnisearch.ts
# docs/archive/: obsidian-rest-api/
```

---

## Summary of All Files Changed

| Action | Path |
|---|---|
| Moved | `obsidian-rest-api/` → `docs/archive/obsidian-rest-api/` |
| Created | `tools/obsidian.ts` |
| Created | `obsidian-cli/SKILL.md` |
| Created | `obsidian-cli/references/cli_reference.md` |
| Created | `obsidian-cli/references/setup.md` |
| Rewritten | `obsidian-dev-notes/SKILL.md` |
| Updated | `AGENTS.md` |
| Updated | `README.md` |
| Unchanged | `tools/omnisearch.ts` |
| Unchanged | `obsidian-dev-notes/references/karpathy-ingest.md` |
