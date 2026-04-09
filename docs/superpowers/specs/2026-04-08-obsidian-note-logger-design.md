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
message.updated     ──┘         │ (Obsidian tool? → update lastObsidianWriteAt)
                                ▼
                         session.idle fires
                                │
                         threshold gate (B)
                         min_tool_calls + min_messages
                         (applied to FULL session counts)
                                │
                         format_transcript
                         (delta filter: only events after
                          lastObsidianWriteAt if set)
                                │
                         write /tmp/opencode-session-<id>.json
                                │
                         shell out → obsidian_note_writer.py
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
             LLM call #1             (if NO → log + skip)
           classify & extract
           → ClassifyResult
           { should_capture, note_type,
             project, topics, reasoning }
           [json_object mode]
                    │
                    ▼
           search Omnisearch :51361
           query: "<project> <topics>"
           filter: Decisions/ or Patterns/
           score ≥ 15, top 2
           read matching notes via CLI
           (skip gracefully if unavailable)
                    │
                    ▼
             LLM call #2
           generate note (enrich or create)
           → { action, path, content,
               existing_path? }
           [json_object mode]
                    │
              ┌─────┴──────┐
              ▼            ▼
           create        enrich
         overwrite=    overwrite=
           false          true
              └─────┬──────┘
                    ▼
           MOC heading insert
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
  startedAt: string              // ISO 8601
  lastObsidianWriteAt: string | null  // ISO 8601 — updated whenever an Obsidian tool fires
}
```

**Delta capture:** `lastObsidianWriteAt` is updated in `tool.execute.after` whenever
`event.tool` matches any of the 17 Obsidian tool names (Option B — any vault touch resets
the window):

```
createNote, readNote, appendToNote, deleteNote, listFiles,
setProperty, readProperty, removeProperty, listProperties,
listTags, listTasks, toggleTask, getBacklinks, getOrphans,
readDailyNote, appendToDailyNote, evalJs
```

The Python worker's `format_transcript` applies this boundary: if `lastObsidianWriteAt`
is set, only `toolCalls` and `messages` with `timestamp > lastObsidianWriteAt` are
included in the transcript sent to the LLM. If `null`, the full session is used. This
ensures the LLM only reasons about the current "work unit" — not the full session history.

**IPC temp file:** At `session.idle` (after threshold gate passes), the plugin writes the
`SessionData` object to `/tmp/opencode-session-<sessionID>.json` as JSON. This exact
TypeScript interface is the contract the Python script reads — field names are identical.
The temp file is deleted by the Python script on successful completion, or by the plugin
on Python script failure (non-zero exit).

**Event hooks:**
- `tool.execute.after` → append to `toolCalls`; update `lastObsidianWriteAt` if Obsidian tool
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

### Gate D — LLM Classify & Extract (in Python script, merged first LLM call)

Classification and context extraction are merged into one call — the LLM reads the
transcript once and returns everything needed for the search and generation steps.

Uses `response_format={"type": "json_object"}` (broadly supported across OpenAI,
Anthropic-compatible, and most Ollama models). Falls back to text parsing if the provider
rejects JSON mode (e.g., older Ollama builds).

**Output schema** (`ClassifyResult` dataclass):
```json
{
  "should_capture": true,
  "note_type": "decision",
  "project": "obsidian-note-logger",
  "topics": ["session.idle", "event trigger", "background agent"],
  "reasoning": "Session documents the architectural choice to use session.idle as the trigger."
}
```

- `should_capture: false` → append a `"skipped: <reason>"` entry to log and exit 0
- `should_capture: true` → proceed to Pre-Write Search with `project` and `topics`
- If LLM returns neither true nor false (malformed) → treat as `false`, log skipped, exit 0

---

## Pre-Write Search (Dedup Check)

Before generating a new note, the Python worker searches the vault for existing notes on
the same project and topic. This implements the `obsidian-dev-notes` core rule:
**"Search Before Creating."**

### Search Step

1. Build query: `f"{project} {' '.join(topics)}"` from the `ClassifyResult`
2. `urllib.request.urlopen(f"http://localhost:51361/search?q={urllib.parse.quote(query)}", timeout=3)`
3. Filter results:
   - Path must start with `Decisions/` or `Patterns/` (matching `note_type`)
   - Score must be ≥ 15 (Omnisearch score scale — filters out weak matches)
4. Read top 2 matching notes via `obsidian read path=<path>`
5. Pass `existing_notes: list[{"path": str, "content": str}]` to generation call

### Graceful Degradation

If Omnisearch is unavailable (any exception: `ECONNREFUSED`, timeout, non-200 response):
- Skip search entirely
- Pass `existing_notes=[]` to generation
- Log `"dedup_check: skipped (Omnisearch unavailable)"` in transaction entry
- Note is created new — no error toast, no exit 1

### Enrich vs Create Decision

If `existing_notes` is non-empty, the generation LLM decides:
- **Enrich:** the session's content clearly extends an existing note on the same topic
- **Create:** the content is sufficiently distinct to warrant a new note

The LLM output includes `action: "enrich" | "create"`. For `"enrich"`, it also returns
`existing_path` (the vault path of the note to update). The Python script then reads the
existing note, passes it along with the new content to overwrite with `overwrite=true`.

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

- Delta transcript (tool calls + messages since `lastObsidianWriteAt`, or full session if null)
- System prompt instructing it to follow the `obsidian-dev-notes` skill schema
- `ClassifyResult` (note type, project, topics, reasoning)
- `existing_notes` — list of `{"path", "content"}` dicts from the search step (may be empty)

**Output JSON schema** (`json_object` mode):
```json
{
  "action": "create",
  "path": "Decisions/2026-04-08-slug.md",
  "content": "---\ntype: decision\n...\n---\n\n## Context\n...",
  "existing_path": null
}
```

For `action: "enrich"`, `existing_path` is set to the vault path being enriched and
`path` holds the same value. `content` is the **complete** replacement content for the
existing note (full note, not a diff).

The Python script parses this JSON with a dedicated try/catch — a JSON parse error is
treated as a failure (logged, red toast, exit 1).

The Python script then:
1. **Create branch** (`action: "create"`): calls `obsidian create path=<path> content=<content> overwrite=false`
2. **Enrich branch** (`action: "enrich"`): calls `obsidian create path=<existing_path> content=<content> overwrite=true`
   - If the read of the existing note fails before overwrite, falls back to `create` at a new path and logs a warning
3. **No separate `property:set` calls** — LLM-generated frontmatter in `content` is authoritative
4. **MOC insert:** The MOC path is resolved as `Projects/<project>.md`. The Python script
   finds the `## Decisions` or `## Patterns` heading and splices a wikilink using the
   read-modify-overwrite pattern. For `enrich`, the wikilink is only added if it doesn't
   already exist in the MOC. If the MOC does not exist, step is skipped with a warning.
5. Appends transaction log entry to `wiki/log.md`.

---

## Transaction Log Format

Each entry appended to `wiki/log.md` (vault-relative):

```markdown
## 2026-04-08 14:32 — Decision captured
- **Session:** ses_abc123
- **Action:** Created | Enriched Decisions/existing-note.md
- **Note:** Decisions/2026-04-08-use-session-idle-for-trigger.md
- **Model:** llama3.2 (ollama)
- **Classified as:** Decision
- **Tool calls logged:** 7
- **Messages logged:** 12
- **Delta window:** since 14:15 (last Obsidian write) | full session
- **Dedup check:** Found 2 related / No matches / Skipped (Omnisearch unavailable)
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
| Classification returns neither YES nor NO | Treat as `should_capture: false`, log skipped entry, exit 0 |
| `obsidian create` CLI non-zero exit | Log error entry, exit 1 |
| MOC not found for wikilink insert | Log warning in entry, skip MOC step, exit 0 |
| Wikilink already in MOC (enrich path) | Skip MOC insert silently — no duplicate links |
| `wiki/log.md` write fails | Silently skip log write, still exit 0 if note succeeded |
| `wiki/log.md` does not exist | Python script uses `obsidian append` which creates the file automatically; no pre-check needed |
| `note_skill` SKILL.md not found | Log warning, proceed with a built-in fallback system prompt that encodes the obsidian-dev-notes schema inline |
| Omnisearch unavailable (any exception) | Skip search, pass `existing_notes=[]`, proceed to create new, log `"dedup_check: skipped (Omnisearch unavailable)"` |
| Enrich: existing note read fails | Fall back to create new note at new path, log warning |

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
