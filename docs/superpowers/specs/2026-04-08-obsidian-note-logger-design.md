# obsidian_note_logger — Design Spec

**Date:** 2026-04-08
**Status:** Approved

## Overview

An OpenCode plugin that automatically captures Decisions and Patterns from development
sessions into an Obsidian vault. The plugin is the automation engine; the note-writing
style is governed by a configurable skill reference (default: `obsidian-dev-notes`).
The user never has to manually trigger note-taking — it happens silently in the background
after every substantive session.

---

## Architecture

Two files. Clean separation of concerns:

```
obsidian_note_logger.ts     ← plugin: event wiring, accumulation, threshold gate
obsidian_note_writer.py     ← worker: LLM classification, note generation, Obsidian CLI
```

The plugin stays under ~100 lines. All heavy logic lives in the Python script, following
the established Builder Kit pattern.

### Data Flow

```
tool.execute.after  ──┐
                      ├─→ in-memory Map<sessionID, SessionData>
message.updated     ──┘         │
                                ▼
                         session.idle fires
                                │
                         threshold gate (B)
                         min_tool_calls + min_messages
                                │
                         write /tmp/opencode-session-<id>.json
                                │
                         shell out → obsidian_note_writer.py
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             LLM call #1            (if NO → skip)
           classify: Decision
           or Pattern? YES/NO
                    │
                    ▼
             LLM call #2
           generate note content
           following obsidian-dev-notes
           schema
                    │
                    ▼
           obsidian CLI shell-out
           createNote + setProperty × N
           (+ MOC heading insert)
                    │
                    ▼
           append to wiki/log.md
                    │
                    ▼
           return result → plugin
                    │
              ┌─────┴─────┐
              ▼           ▼
         TUI toast    OS notify
                      (opt-in)
```

---

## Session Accumulation

In-memory store per session. The plugin maintains `Map<string, SessionData>` keyed by
`sessionID`. This same structure is serialized as-is to the IPC temp file.

```typescript
interface ToolCall {
  tool: string        // tool name, e.g. "bash", "write"
  input: unknown      // raw args object from event
  output: unknown     // raw result from event
  timestamp: string   // ISO 8601
}

interface Message {
  id: string          // message ID — used for upsert dedup
  role: string        // "user" | "assistant"
  content: string     // full message text (last streamed value)
  timestamp: string   // ISO 8601
}

interface SessionData {
  sessionID: string
  toolCalls: ToolCall[]
  messages: Message[]
  startedAt: string   // ISO 8601
}
```

**IPC temp file:** At `session.idle` (after threshold gate passes), the plugin writes the
`SessionData` object to `/tmp/opencode-session-<sessionID>.json` as JSON. This exact
TypeScript interface is the contract the Python script reads — field names are identical.
The temp file is deleted by the Python script on successful completion, or by the plugin
on Python script failure (non-zero exit).

**Event hooks:**
- `tool.execute.after` → append to `toolCalls`
- `message.updated` → upsert by `event.messageID` into `messages` (handles streaming — last write wins)
- `session.idle` → run threshold gate, write temp file, shell out to Python script
- `session.deleted` → delete in-memory `SessionData` entry only (temp file already handled by `session.idle` path or never created if threshold not met)

---

## Event Semantics

`session.idle` — fires once after the OpenCode agent finishes its full response cycle
(confirmed present in the plugin API event table as "Session finished responding — agent
is idle"). It carries at minimum `event.sessionID`. It fires after *every* agent response,
including trivial one-liners — hence the need for Gate B.

`tool.execute.after` — carries `event.tool` (tool name string), `event.input` (args
object), `event.output` (result), `event.messageID`, `event.sessionID`.

`message.updated` — carries `event.messageID`, `event.sessionID`, and a content payload.
The plugin extracts the content string from `event.content` (top-level string field).
If the field is absent or nested differently at runtime, the plugin logs a warning and
stores an empty string — it never throws.

---

## Filtering Gates

### Gate B — Threshold (cheap, synchronous, in plugin)

- Skip session if `toolCalls.length < config.min_tool_calls` (default: 2)
- Skip session if `messages.length < config.min_messages` (default: 3)
- Skipped sessions are silently discarded (no toast, no log entry)

### Gate D — LLM Classification (in Python script, first LLM call)

System prompt: *"You are a classifier. Given this OpenCode session transcript, answer
YES or NO: does this session contain a Decision or Pattern worth capturing in a
developer knowledge base? Reply with YES or NO followed by one sentence of reasoning."*

The Python script parses the classification response with a simple `strip().upper().startswith("YES")`
check — no regex, no structured output required. The remainder of the response is captured
as `classification_reasoning` for the log entry.

- If NO → append a `"skipped: <reason>"` entry to log (if `log_enabled`) and exit 0
- If YES → proceed to note generation

---

## LLM Configuration & Provider Support

Config read from `opencode.json` under `obsidian_note_logger` key. Python script uses
the `openai` library with configurable `base_url` for both cloud and local providers.

### Model Resolution Order

When `model` is `null` in config, the Python script resolves the model in this order:
1. `OPENCODE_MODEL` env var (set by OpenCode's `shell.env` hook — carries the main session model)
2. `ANTHROPIC_DEFAULT_MODEL` env var
3. Hardcoded fallback: `"claude-haiku-4-5"` (ensures the plugin always works without config)

### API Key Resolution Order

1. `api_key` in config block (explicit override)
2. `ANTHROPIC_API_KEY` env var (inherited from main agent via `shell.env` hook)
3. `OPENAI_API_KEY` env var
4. Auto-set to `"ollama"` when `base_url` contains `localhost:11434`

### Ollama Support

Full support via OpenAI-compatible endpoint. User sets:

```jsonc
"model": "llama3.2",
"base_url": "http://localhost:11434/v1",
"api_key": "ollama"
```

No additional dependencies — same `openai` Python library handles it.

---

## Note Generation

The second LLM call receives:

- Full session transcript (tool calls + messages)
- System prompt instructing it to follow the `obsidian-dev-notes` skill schema
- Classification result from Gate D
- Target note type: Decision or Pattern

Output is a JSON object with two keys:
```json
{
  "path": "Decisions/2026-04-08-slug.md",
  "content": "---\ntype: decision\n...\n---\n\n## Context\n..."
}
```

The LLM generates the complete markdown including YAML frontmatter inline. The Python
script parses this JSON with a dedicated try/catch — a JSON parse error is treated as
a classification failure (logged, toast shown, exit 0).

The Python script then:
1. Calls `obsidian create path=<path> content=<content> overwrite=false` — the full
   markdown (including frontmatter) is passed as `content`. The Obsidian CLI parses
   frontmatter from the note body on create. **No separate `property:set` calls are
   made** — the LLM-generated frontmatter in `content` is the authoritative source.
2. **MOC insert:** The project MOC is located by reading the `project` frontmatter field
   from the generated note. The MOC path is resolved as `Projects/<project>.md` (vault-
   relative, per `obsidian-dev-notes` folder schema). The Python script calls
   `obsidian read path=Projects/<project>.md`, finds the `## Decisions` or `## Patterns`
   heading (matching the note type), and splices a wikilink after it using the read-
   modify-overwrite pattern (`obsidian create ... overwrite=true`). If the MOC does not
   exist, the step is skipped and a warning is appended to the log entry — note creation
   still succeeds.
3. Appends transaction log entry to `wiki/log.md`.

---

## Transaction Log Format

Each entry appended to `wiki/log.md` (vault-relative):

```markdown
## 2026-04-08 14:32 — Decision captured
- **Session:** ses_abc123
- **Note:** Decisions/2026-04-08-use-session-idle-for-trigger.md
- **Model:** llama3.2 (ollama)
- **Classified as:** Decision
- **Tool calls logged:** 7
- **Messages logged:** 12
- **Classification reasoning:** Session documents an architectural trigger choice
```

Failed writes append:

```markdown
## 2026-04-08 14:35 — ERROR: write failed
- **Session:** ses_def456
- **Error:** obsidian CLI returned non-zero exit code
- **Raw:** <error message>
```

---

## Error Handling

### Python Script Crash (plugin side)
The plugin shells out via `Bun.$\`python3 ${scriptPath} ${transcriptPath}\``. If the
script exits non-zero, the plugin:
1. Shows a red TUI toast: `"Obsidian note failed — check wiki/log.md"`
2. Logs to `client.app.log("error", ...)` with the exit code and stderr
3. Deletes the temp file `/tmp/opencode-session-<id>.json`
4. Does **not** throw — failure is always silent from the user's perspective except for
   the toast

### Python Script Internal Failures
The Python script handles its own errors and always exits 0 unless a catastrophic/
unrecoverable error occurs. Internal failure modes and their handling:

| Failure | Handling |
|---|---|
| Temp file missing / unreadable | Exit 1 (plugin shows red toast) |
| JSON parse error on temp file | Exit 1 (plugin shows red toast) |
| LLM API call fails (network, auth) | Log error entry, exit 1 |
| LLM returns malformed JSON for note | Log error entry, exit 1 |
| Classification returns neither YES nor NO | Treat as NO, log skipped entry, exit 0 |
| `obsidian create` CLI non-zero exit | Log error entry, exit 1 |
| MOC not found for wikilink insert | Log warning in entry, skip MOC step, exit 0 |
| `wiki/log.md` write fails | Silently skip log write, still exit 0 if note succeeded |
| `wiki/log.md` does not exist | Python script uses `obsidian append` which creates the file automatically; no pre-check needed |
| `note_skill` SKILL.md not found | Log warning, proceed with a built-in fallback system prompt that encodes the obsidian-dev-notes schema inline |

### Temp File Lifecycle
- Created: by plugin at `session.idle` after threshold gate passes
- Deleted on success: by Python script after all steps complete
- Deleted on plugin-detected failure: by plugin after non-zero exit from Python script
- Never accumulates: each `session.idle` uses a unique `sessionID`-keyed filename

---

## Notifications

**In-app (always on when `toast_enabled: true`):**
- Success: green toast → `"Note written: Decisions/2026-04-08-<slug>.md"`
- Skipped (threshold): no notification
- Skipped (classification): no notification
- Error: red toast → `"Obsidian note failed — check wiki/log.md"`

**OS-level (opt-in via `os_notify: true`):**
- Linux: `notify-send "OpenCode → Obsidian" "<message>"`
- macOS: `osascript -e 'display notification "<message>" with title "OpenCode"'`
- Detected automatically from `process.platform`

---

## Configuration Schema

Full config block in `opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "obsidian_note_logger": {
    "model": null,           // null = inherit main session model env var
    "base_url": null,        // null = cloud; "http://localhost:11434/v1" = Ollama
    "api_key": null,         // null = inherit from env

    "vault": null,           // null = active Obsidian vault
    "note_skill": "obsidian-dev-notes",  // skill whose schema governs note structure;
                                         // the Python script reads the named skill's
                                         // SKILL.md from .opencode/skills/<name>/SKILL.md
                                         // and includes it verbatim in the LLM system
                                         // prompt for both Gate D and note generation

    "min_tool_calls": 2,
    "min_messages": 3,

    "log_path": "wiki/log.md",
    "log_enabled": true,

    "toast_enabled": true,
    "os_notify": false
  }
}
```

---

## Files to Create

| File | Location | Purpose |
|---|---|---|
| `obsidian_note_logger.ts` | `.opencode/plugins/` | Plugin: event hooks, accumulation, threshold gate |
| `obsidian_note_writer.py` | `.opencode/tools/` | Worker: LLM calls, Obsidian CLI shell-out, log |
| `opencode.json` | project root | Add `obsidian_note_logger` config block with defaults |
| `README.md` | project root | Add 3 config examples (default, Ollama, Haiku) |

---

## README Config Examples

### Default (inherits main model)

```jsonc
"obsidian_note_logger": {
  "model": null,
  "base_url": null,
  "api_key": null
}
```

### Local AI with Ollama

```jsonc
"obsidian_note_logger": {
  "model": "llama3.2",
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama"
}
```

### Smaller cloud model (Anthropic Haiku)

```jsonc
"obsidian_note_logger": {
  "model": "claude-haiku-4-5",
  "base_url": null,
  "api_key": null
}
```

---

## Out of Scope (explicitly deferred)

- `raw/` folder cron ingestion (separate plugin, separate spec)
- `session.diff` integration (investigate post-MVP)
- `todo.updated` trigger (undocumented payload, deferred)
- Web UI for log viewing
- Note editing / updating existing notes (create-only for v1)
