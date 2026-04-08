# AGENTS.md — Coding Agent Reference

This repository provides **OpenCode skills and tools** for Obsidian integration. It is a documentation-first project with one TypeScript tool file and Markdown skill definitions consumed by OpenCode agents.

---

## Repository Structure

```
obsidian-rest-api/    # Skill: Obsidian Local REST API — SKILL.md + references/
obsidian-dev-notes/   # Skill: structured developer knowledge — SKILL.md + references/
tools/omnisearch.ts   # OpenCode tool (TypeScript, Bun runtime)
docs/                 # General documentation
pyproject.toml        # Python package metadata (no source files)
.env.example          # Template: obsidian_api_keys=...
```

---

## Build & Install Commands

```bash
uv pip install -e .          # Install Python deps (preferred)
pip install -r requirements.txt   # Alternative

# Deploy to OpenCode
cp -r obsidian-rest-api ~/.claude/skills/
cp -r obsidian-dev-notes ~/.claude/skills/
cp tools/omnisearch.ts ~/.claude/tools/

bun check tools/omnisearch.ts   # Type-check a tool
bun run tools/omnisearch.ts     # Run a tool directly
```

---

## Testing

No test suite is configured. If tests are added:

```bash
pytest tests/                          # All Python tests
pytest tests/test_foo.py::test_bar -v  # Single Python test
bun test                               # All TypeScript tests (Bun built-in)
bun test tools/omnisearch.test.ts      # Single TypeScript test file
```

---

## TypeScript Tool Conventions (`tools/*.ts`)

`tools/omnisearch.ts` is the canonical example. All tools use the OpenCode plugin API.

### Imports & Structure

```typescript
import { tool } from "@opencode-ai/plugin"   // only required import

interface SearchResult {   // PascalCase interfaces, after imports
  score: number
  path: string
}

export const myTool = tool({   // camelCase named export
  description: "Verb phrase. State WHEN to use this tool explicitly.",
  args: {
    query: tool.schema.string().describe("What the user is searching for."),
    limit: tool.schema.number().int().positive().default(10).describe("Max results."),
  },
  async execute(args) {
    const { query, limit } = args   // always destructure at top
    // ...
    return JSON.stringify(result, null, 2)   // always return JSON string
  },
})
```

### Error Handling

All errors are **returned as JSON — never thrown**. OpenCode must be able to parse the output.

```typescript
try {
  const response = await fetch(url)
  if (!response.ok) {
    return JSON.stringify({
      error: "API request failed",
      status: response.status,
      statusText: response.statusText,
    }, null, 2)
  }
  return JSON.stringify(await response.json(), null, 2)
} catch (error) {
  const err = error as Error   // cast, never use `any`
  if (err.message.includes("ECONNREFUSED")) {
    return JSON.stringify({
      error: "Cannot connect to Obsidian",
      details: "Ensure the Local REST API plugin is running.",
      originalError: err.message,
    }, null, 2)
  }
  return JSON.stringify({ error: "Operation failed", message: err.message }, null, 2)
}
```

- Check `response.ok` before parsing the body.
- Include actionable `details` for user-fixable failures.
- Include `originalError` only when it aids debugging.

### Formatting

- 2-space indentation; no semicolons (match the style of the file you're editing).
- `const`/`let` only — never `var`.
- `async/await` over `.then()` chains.
- Use `Bun.$\`command\`` for shell operations (not `child_process`).

---

## Skill File Conventions (`*/SKILL.md`)

### Frontmatter

```yaml
---
name: skill-name-kebab-case   # must match directory name
description: >
  Verb phrase. Explicitly state WHEN to use this skill (triggers) and
  what it enables. Be specific — this is used for skill matching.
---
```

Bad: `"Helps with Obsidian."` — Good: `"Interact with an Obsidian vault to create, read, update, or delete notes using the Local REST API. Use when managing vault content programmatically."`

### Content Structure

```markdown
## Overview        — one-paragraph summary
## When to Use     — bullet list of exact trigger conditions
## Workflow        — numbered steps; reference tool calls in backticks
## Reference       — links to files in references/
```

- Write for an AI reader: be explicit, not implicit.
- Numbered lists for sequential steps; bullet lists for options.
- Include concrete examples (curl, tool calls, frontmatter templates).

### Reference Files (`references/*.md`)

| File | Contents |
|---|---|
| `api_endpoints.md` | Method, path, params, response for every endpoint |
| `authentication.md` | Plugin setup and API key configuration |
| `examples.md` | Working curl/code examples, one per section header |

Use fenced code blocks with language tags (`bash`, `json`, `typescript`).

---

## Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| TypeScript tool exports | `camelCase` | `refreshIndex`, `openSearch` |
| TypeScript interfaces | `PascalCase` | `SearchResult`, `SearchMatch` |
| Skill directories | `kebab-case` | `obsidian-rest-api/` |
| Skill files | `SKILL.md` (uppercase) | `obsidian-dev-notes/SKILL.md` |
| Reference docs | `snake_case.md` | `api_endpoints.md` |
| Env vars | `snake_case` | `obsidian_api_keys` |

---

## Environment & Configuration

```bash
cp .env.example .env   # then fill in values
# obsidian_api_keys=your-api-key-here
```

Default ports: REST API → `27123`, Omnisearch HTTP API → `51361`. Never commit `.env`.

---

## Contributing

1. Match the style of the file you are editing — do not reformat unrelated lines.
2. Update documentation when adding or changing a tool or skill.
3. Skills must have a trigger-specific `description` in YAML frontmatter.
4. Tools must handle all errors as JSON return values, never as thrown exceptions.
5. New tools → `tools/`; new skills → top-level `kebab-case/` dir with `SKILL.md` + `references/`.
6. Do not add runtime dependencies without updating `pyproject.toml` and `requirements.txt`.
