---
name: init-new-moc
description: >
  Use when the user wants to start a new project with the obsidian_note_logger
  pipeline. Triggers: "new project", "init project", "create MOC", "setup new
  project", "start tracking a new project", "configure for new project",
  "new moc", "initialize project". Walks the user through inference provider
  selection (OpenRouter or Ollama), all plugin config fields in opencode.json,
  creates the project MOC in Obsidian, and verifies the full pipeline is healthy.
compatibility: opencode
license: MIT
---

# Init New MOC

Guided setup wizard for starting a new project with the `obsidian_note_logger`
pipeline. Walks the user through every config field, creates the project MOC,
and verifies the full pipeline is healthy before finishing.

---

## Overview

When a user starts a new project, this skill:

1. Collects project identity (name → kebab slug, vault)
2. Asks the user to choose an inference provider (OpenRouter or Ollama)
3. Walks through session capture thresholds and notification preferences
4. Verifies the full pipeline — Ollama, Omnisearch, vault, model, Modelfile sync
5. Creates the project MOC in Obsidian using `obsidian_createNote`
6. Previews config diff and writes `opencode.json` atomically on confirm

---

## Stage 1: Project Identity

Ask the user:

1. **Project name** — human readable (e.g. "My Auth Service")
   - Derive kebab slug automatically: `my-auth-service`
   - Show derived slug and ask: "Does this slug look right, or would you like to customize it?"

2. **Vault name** — show current value from `opencode.json`:
   ```
   Current vault: Diddys_Diaries
   Press Enter to keep, or type a new vault name:
   ```

3. **One-sentence overview** — used for the MOC Overview section
   - "Describe this project in one sentence:"

4. **Domain tags** — 1-3 short tags for the MOC frontmatter
   - "Enter 1-3 domain tags separated by commas (e.g. typescript, api, cli):"

---

## Stage 2: Inference Provider

Present the user with exactly two choices:

```
Which inference provider should the note-taker use for this project?

A) OpenRouter (cloud)
   Model: anthropic/claude-haiku-4-5
   Key:   read automatically from ~/.local/share/opencode/auth.json
   Best for: reliable cloud inference, no local GPU required

B) Ollama (local)
   Model: notetaker (nemotron-cascade-2, 250K context, temperature=0)
   URL:   http://localhost:11434/v1
   Best for: fully local, private, no API costs
   Requires: Ollama running with `notetaker` model created
```

**Based on choice, set these config fields:**

| Field | OpenRouter | Ollama |
|---|---|---|
| `base_url` | `https://openrouter.ai/api/v1/` | `http://localhost:11434/v1` |
| `api_key` | `null` (auto-read from auth.json) | `"ollama"` |
| `model` | `"anthropic/claude-haiku-4-5"` | `"notetaker"` |
| `ollama_model` | `null` | `"notetaker"` |

---

## Stage 3: Session Capture Thresholds

Show current defaults and explain what they do:

```
Session capture thresholds control when the pipeline fires.
Lower = notes on shorter sessions. Higher = only substantial sessions.

min_tool_calls: 10   (minimum tool calls in a session before capturing)
min_messages:   8    (minimum messages in a session before capturing)

Keep defaults? (y/n)
```

If no, ask for new values. Warn:
- If `min_tool_calls < 5`: "This may produce notes on very short sessions — lots of noise"
- If `min_tool_calls > 30`: "This is very high — the pipeline may rarely fire"

---

## Stage 4: Notifications

Ask each in sequence (y/n):

```
Enable TUI toast notifications when notes are written? [Y/n]
Enable OS desktop notifications after note written? [Y/n]
Enable audit log in vault? [Y/n]  (strongly recommended — tracks every note written)
Audit log path in vault? [wiki/log.md]  (press Enter to keep default)
```

---

## Stage 5: Verification

Run these checks before creating the MOC or writing config.
Report pass ✅ / warn ⚠ / fail ❌ for each:

### 5a: Vault reachable
- Use `obsidian_listFiles` to verify vault is reachable
- ❌ Fail → ask user to confirm correct vault name before continuing

### 5b: Omnisearch reachable
- Use `omnisearch_search({ query: "test" })`
- ✅ Returns results → Omnisearch up, dedup search will work
- ⚠ Fails → "Omnisearch unavailable — dedup search will be skipped, notes will still be written"

### 5c: Existing MOC check
- Use `omnisearch_search({ query: "<project-name> MOC" })` — look for hits in `Projects/`
- If found → "A MOC already exists at `Projects/<Name>-MOC.md`. Use existing or create new?"
- If not found → proceed to create

### 5d: Ollama checks (only if Ollama chosen in Stage 2)
```bash
curl -s http://localhost:11434/api/tags
```
- ❌ Not reachable → "Ollama is not running. Start it with `ollama serve` before continuing."
- ✅ Reachable → check if `notetaker` model exists in response
  - ❌ Missing → "Run: `ollama create notetaker -f .opencode/tools/Modelfiles/notetaker.Modelfile`"
  - ✅ Exists → pass

### 5e: Modelfile context limit sync (only if Ollama chosen)
Read `.opencode/tools/Modelfiles/notetaker.Modelfile` and extract `num_ctx`.
Compare against `provider.ollama.models.notetaker.limit.context` in `opencode.json`.
- ⚠ Mismatch → "Modelfile num_ctx=250000 but opencode.json limit.context=131072.
  Will update opencode.json to match during config write."

### 5f: OpenRouter key check (only if OpenRouter chosen)
Read `~/.local/share/opencode/auth.json` and check `openrouter.key` is present.
- ❌ Missing → "No OpenRouter key found. Run `/connect` in the OpenCode TUI and select OpenRouter."
- ✅ Present → show masked: `sk-or-...XXXX` → pass

### 5g: note_skill exists
Check `.opencode/skills/obsidian-dev-notes/SKILL.md` (or whatever `note_skill` is set to).
- ⚠ Missing → "note_skill not found — note generation may use default style"

---

## Stage 6: MOC Creation

After all checks pass (or user acknowledges warnings), create the MOC.

Derive the PascalCase MOC filename from the kebab slug:
- `my-auth-service` → `MyAuthService` → `Projects/MyAuthService-MOC.md`

Use `obsidian_createNote` with this template (fill values from Stage 1):

```markdown
---
type: moc
project: <kebab-slug>
status: in-progress
tags: [project, <tag-1>, <tag-2>]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# <Project Name> — Project MOC

## Overview
<One sentence overview from Stage 1>

## Key Concepts

## Architecture Decisions

## Patterns

## Implementation Notes

## Tasks
- [ ] Initial setup complete

## Learnings

## Retrospectives

## Related Projects
```

Call: `obsidian_createNote({ path: "Projects/<PascalName>-MOC.md", content: <above>, overwrite: false })`

Confirm: "MOC created at `Projects/<PascalName>-MOC.md`"

---

## Stage 7: Config Preview + Write

Show a summary of what will be written:

```
The following changes will be saved to opencode.json:

  project:        <new-slug>
  vault:          <vault>
  base_url:       <url>
  api_key:        <"ollama" or null>
  model:          <model>
  ollama_model:   <model or null>
  min_tool_calls: <N>
  min_messages:   <N>
  toast_enabled:  <true/false>
  os_notify:      <true/false>
  log_enabled:    <true/false>
  log_path:       <path>

Save these settings? (yes / no / edit)
```

On **yes**: write `opencode.json` atomically
- Read full file → update `plugin[0][1].obsidian_note_logger` fields
- If 5e Modelfile mismatch detected: also update
  `provider.ollama.models.notetaker.limit.context` and
  `provider.ollama.models.note-drift.limit.context` to match Modelfile value
- Write back with `json.dumps(indent=2)` + trailing newline

On **no**: abort — tell user no files were modified.

On **edit**: ask which stage to return to, loop back, re-run verification.

---

## Config Field Reference

```
project          → kebab-case slug; routes notes to the correct MOC in Obsidian
vault            → name of your Obsidian vault directory
base_url         → LLM endpoint (OpenRouter: https://openrouter.ai/api/v1/ | Ollama: http://localhost:11434/v1)
api_key          → "ollama" for local inference, null to auto-read from auth.json for cloud
model            → LLM model name sent to the API
ollama_model     → Ollama model alias (only used when base_url is localhost:11434)
min_tool_calls   → minimum tool calls a session needs before the pipeline fires
min_messages     → minimum messages a session needs before the pipeline fires
log_enabled      → write an audit entry to wiki/log.md after every note written
log_path         → path inside vault for the audit log file
toast_enabled    → show TUI toast notifications when a note is written or on error
os_notify        → show an OS desktop notification after a note is written
note_skill       → which skill teaches the LLM note format (default: obsidian-dev-notes)
```

---

## Important Notes

- Non-destructive until Stage 7 — no files are changed until the user confirms
- If the user exits before Stage 7, nothing is written
- Ollama checks (5d, 5e) are skipped entirely if OpenRouter is chosen in Stage 2
- OpenRouter check (5f) is skipped entirely if Ollama is chosen
- MOC is created before config is written — if config write fails, MOC still exists
- After saving config, remind the user: **"Restart the OpenCode server to pick up the new plugin config"**
- Run `@notedrift` after setup to link the new MOC into the vault graph
