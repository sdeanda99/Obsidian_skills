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

**Exports (17):** `createNote`, `readNote`, `appendToNote`, `deleteNote`, `listFiles`,
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
