---
name: init-new-moc
description: >
  Use when the user wants to start a new project with the obsidian_note_logger
  pipeline. Triggers: "new project", "init project", "create MOC", "setup new
  project", "start tracking a new project", "configure for new project",
  "new moc", "initialize project". Walks the user through install level
  selection (project or global), inference provider selection (OpenRouter or
  Ollama), all plugin config fields in opencode.json, creates the project MOC
  in Obsidian, and verifies the full pipeline is healthy.
compatibility: opencode
license: MIT
---

# Init New MOC

Guided setup wizard for starting a new project with the `obsidian_note_logger`
pipeline. Walks the user through install level, every config field, creates the
project MOC, and verifies the full pipeline is healthy before finishing.

---

## Overview

When a user starts a new project, this skill:

1. Asks where to install (project-level or global)
2. Collects project identity (name → kebab slug, vault)
3. Asks the user to choose an inference provider (OpenRouter or Ollama)
4. Walks through session capture thresholds and notification preferences
5. Verifies the full pipeline — Ollama, Omnisearch, vault, model, Modelfile sync
6. Creates the project MOC in Obsidian using `obsidian_createNote`
7. Previews config diff and writes the target `opencode.json` atomically on confirm

---

## Stage 0: Install Level

Before anything else, ask the user where to install:

```
Where do you want to install the obsidian_note_logger plugin?

A) Project-level (recommended for first-time setup)
   Config lives in THIS repo's opencode.json
   Best for: different vault/model/project settings per repo
   Config file: <current-working-dir>/opencode.json

B) Global
   Plugin available in ALL repos on this machine
   Best for: one vault across all projects, configure once
   Config file: ~/.config/opencode/opencode.json
   Note: each project repo will still need a minimal opencode.json
         with just "project" (and optionally "vault") to identify itself
```

**If Project-level (A):**
- Target config file: `<worktree>/opencode.json`
- Detect the absolute path to the global plugin:
  ```bash
  # Resolve ~ to actual home directory
  PLUGIN_PATH="$HOME/.config/opencode/plugins/obsidian_note_logger.ts"
  ```
  Use this absolute path (e.g. `/home/username/.config/opencode/plugins/obsidian_note_logger.ts`)
  as the plugin path in the config — NOT a tilde path (tilde causes npm lookup errors in OpenCode).
- Proceed directly to Stage 1

**If Global (B):**
- Detect absolute plugin path: `$HOME/.config/opencode/plugins/obsidian_note_logger.ts`
- Check if plugin file exists at that path
- If NOT found, the user needs to clone the Obsidian_skills repo and run the install.
  Show these commands and ask user to run them, then confirm:
  ```bash
  # Clone the repo (skip if already cloned)
  git clone https://github.com/sdeanda99/Obsidian_skills.git ~/Work/Obsidian_skills

  REPO=~/Work/Obsidian_skills
  mkdir -p ~/.config/opencode/plugins \
            ~/.config/opencode/tools \
            ~/.config/opencode/tools/Modelfiles \
            ~/.config/opencode/agents \
            ~/.config/opencode/skills
  cp $REPO/tools/obsidian_note_logger.ts  ~/.config/opencode/plugins/  2>/dev/null || \
  cp $REPO/.opencode/plugins/obsidian_note_logger.ts ~/.config/opencode/plugins/
  cp $REPO/tools/obsidian_note_writer.py  ~/.config/opencode/tools/    2>/dev/null || \
  cp $REPO/.opencode/tools/obsidian_note_writer.py   ~/.config/opencode/tools/
  cp $REPO/.opencode/tools/Modelfiles/*.Modelfile ~/.config/opencode/tools/Modelfiles/
  cp $REPO/.opencode/agents/notedrift.md ~/.config/opencode/agents/
  cp -r $REPO/.opencode/skills/init-new-moc ~/.config/opencode/skills/
  cp -r $REPO/.opencode/skills/notedrift   ~/.config/opencode/skills/
  ```
  Wait for user to confirm files are copied before continuing.
- Target config file: `~/.config/opencode/opencode.json`
- Use absolute plugin path (no tilde) in all config writes
- Proceed to Stage 1

**After Stage 7 (config write), if Global was chosen, show this message:**
```
Global install complete!

For each new project repo, run init-new-moc in that repo (choose Project-level),
OR manually create a minimal opencode.json with just the project-specific overrides:

{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [[
    "/home/<your-username>/.config/opencode/plugins/obsidian_note_logger.ts",
    {
      "obsidian_note_logger": {
        "project": "your-project-slug",
        "vault": "YourVault"
      }
    }
  ]]
}

IMPORTANT: Use the absolute path (no ~) for the plugin path.
Restart the OpenCode server to pick up the new config.
```

---

## Stage 1: Project Identity

Ask the user:

1. **Project name** — human readable (e.g. "My Auth Service")
   - Derive kebab slug automatically: `my-auth-service`
   - Show derived slug and ask: "Does this slug look right, or would you like to customize it?"

2. **Vault name** — show current value from target config (or null if not set):
   ```
   Current vault: null (not set)
   Enter your Obsidian vault name (the directory name of your vault):
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
- Use `omnisearch_search({ query: "test", limit: 1 })`
- ✅ Returns → Omnisearch up, dedup search will work
- ⚠ Fails → "Omnisearch unavailable — dedup search will be skipped, notes will still be written"

### 5c: Existing MOC check
- Use `omnisearch_search({ query: "<project-name> MOC", limit: 5 })` — look for hits in `Projects/`
- If found → "A MOC already exists at `Projects/<Name>-MOC.md`. Use existing or create new?"
- If not found → proceed to create

### 5d: Ollama checks (only if Ollama chosen in Stage 2)
```bash
curl -s http://localhost:11434/api/tags
```
- ❌ Not reachable → "Ollama is not running. Start it with `ollama serve` before continuing."
- ✅ Reachable → check if `notetaker` model exists in response
  - ❌ Missing → show: `ollama create notetaker -f .opencode/tools/Modelfiles/notetaker.Modelfile`
  - ✅ Exists → pass

### 5e: Modelfile context limit sync (only if Ollama chosen)
Read `.opencode/tools/Modelfiles/notetaker.Modelfile` (or `~/.config/opencode/tools/Modelfiles/notetaker.Modelfile` for global install).
Extract `num_ctx` value. Compare against target config's `provider.ollama.models.notetaker.limit.context`.
- ⚠ Mismatch → "Will update opencode.json limit.context to match Modelfile during config write."

### 5f: OpenRouter key check (only if OpenRouter chosen)
Read `~/.local/share/opencode/auth.json` and check `openrouter.key` is present and non-empty.
- ❌ Missing → "No OpenRouter key found. Run `/connect` in the OpenCode TUI and select OpenRouter."
- ✅ Present → show masked: `sk-or-...XXXX` → pass

### 5g: note_skill exists
Check that `.opencode/skills/obsidian-dev-notes/SKILL.md` (or global equivalent) exists.
- ⚠ Missing → "note_skill 'obsidian-dev-notes' not found — note generation may use default style"

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

Show a summary of what will be written to the target config file:

```
The following will be saved to <target-config-file>:

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

On **yes**: write target config atomically.

The write behavior differs by install level:

### Project-level write

Write a **minimal** `<worktree>/opencode.json` that only overrides project-specific
fields. All other settings (model, thresholds, notifications) inherit from the global
config via OpenCode's merge behaviour:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [[
    "/home/<username>/.config/opencode/plugins/obsidian_note_logger.ts",
    {
      "obsidian_note_logger": {
        "project": "<kebab-slug>",
        "vault": "<vault>"
      }
    }
  ]]
}
```

CRITICAL: Use the **absolute path** for the plugin (expand `~` to the actual home
directory). Tilde paths cause npm lookup errors in OpenCode. Detect with:
```bash
echo "$HOME/.config/opencode/plugins/obsidian_note_logger.ts"
```

### Global write

Write the **full config** to `~/.config/opencode/opencode.json`. The global config
must contain ALL fields of the `NoteLoggerConfig` TypeScript interface — omitting
`project` or `ollama_model` causes them to be silently dropped:

```json
{
  "obsidian_note_logger": {
    "project":        null,
    "model":          "<model>",
    "base_url":       "<url>",
    "api_key":        "<key or null>",
    "ollama_model":   "<model or null>",
    "vault":          "<vault>",
    "note_skill":     "obsidian-dev-notes",
    "min_tool_calls": 10,
    "min_messages":   8,
    "log_path":       "wiki/log.md",
    "log_enabled":    true,
    "toast_enabled":  true,
    "os_notify":      true,
    "rest_api_key":   null,
    "rest_api_port":  27123
  }
}
```

Note: `project` is `null` in global config — each project repo overrides it.
Note: `rest_api_key` is only needed if the Obsidian Local REST API plugin requires authentication. Leave `null` to skip REST and use filesystem writes.

Also add `provider.ollama` block if Ollama chosen. If 5e Modelfile mismatch detected,
update `provider.ollama.models.notetaker.limit.context` and
`provider.ollama.models.note-drift.limit.context` to match Modelfile `num_ctx`.

On **no**: abort — tell user no files were modified.

On **edit**: ask which stage to return to, loop back, re-run verification.

**After writing**, remind: "Restart the OpenCode server to pick up the new plugin config."

If Global install was chosen, show the per-project override snippet from Stage 0.

---

## Config Field Reference

```
project          → kebab-case slug matching your MOC filename prefix (e.g. obsidian-note-logger)
                   null = pipeline bails with prompt to run init-new-moc
vault            → name of your Obsidian vault directory (e.g. Diddys_Diaries)
base_url         → LLM endpoint: https://openrouter.ai/api/v1/ or http://localhost:11434/v1
api_key          → "ollama" for local, null to auto-read from auth.json for cloud
model            → LLM model name sent to the API
ollama_model     → Ollama model alias (only used when base_url contains localhost:11434)
min_tool_calls   → minimum tool calls a session needs before the pipeline fires
min_messages     → minimum messages a session needs before the pipeline fires
log_enabled      → write an audit entry to wiki/log.md after every note written
log_path         → path inside vault for the audit log file
toast_enabled    → show TUI toast notifications when a note is written or on error
os_notify        → show an OS desktop notification after a note is written
note_skill       → which skill teaches the LLM note format (default: obsidian-dev-notes)
rest_api_key     → Obsidian Local REST API key (null = skip REST, write via filesystem)
rest_api_port    → Obsidian Local REST API port (default: 27123)
```

---

## Important Notes

- Non-destructive until Stage 7 — no files are changed until the user confirms
- If the user exits before Stage 7, nothing is written
- Ollama checks (5d, 5e) are skipped entirely if OpenRouter is chosen in Stage 2
- OpenRouter check (5f) is skipped entirely if Ollama is chosen
- MOC is created before config is written — if config write fails, MOC still exists
- After saving config, always remind: **"Restart the OpenCode server to pick up the new plugin config"**
- Run `@notedrift` after setup to link the new MOC into the vault graph
