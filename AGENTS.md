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
  obsidian.ts         # OpenCode tool: vault CRUD via Obsidian CLI (17 exports)

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
// Bun Shell treats array interpolation as separate arguments (not shell-expanded).
// Each string element becomes its own argv slot — safe for user-provided content.
async function run(args: string[]): Promise<string> {
  return (await Bun.$`${args}`.text()).trim()
}

// Build args as an array — encode newlines/tabs per CLI requirements
function buildArgs(vault, command, params) {
  const args = ["obsidian"]
  if (vault) args.push(`vault=${vault}`)
  args.push(command)
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === false) continue
    if (val === true) args.push(key)
    else args.push(`${key}=${String(val).replace(/\n/g, "\\n").replace(/\t/g, "\\t")}`)
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
- Wrap `JSON.parse()` calls in their own try/catch — parse errors are distinct from CLI errors

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
5. Wrap `JSON.parse()` calls in their own try/catch to surface raw CLI output on failure.
6. New tools → `tools/`; new skills → top-level `kebab-case/` dir with `SKILL.md` + `references/`.
7. Do not add runtime dependencies without updating `pyproject.toml` and `requirements.txt`.
8. Archived content lives in `docs/archive/` — do not delete, reference it from AGENTS.md.
