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
