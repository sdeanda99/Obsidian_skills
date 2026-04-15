import type { PluginInput } from "@opencode-ai/plugin"
import { resolve } from "path"
import { writeFileSync, unlinkSync, readFileSync } from "fs"
import { tmpdir } from "os"

// ── Types ──────────────────────────────────────────────────────────────────

interface ToolCall {
  tool: string
  input: unknown
  output: unknown
  timestamp: string
}

interface Message {
  id: string
  role: string
  content: string
  timestamp: string
}

interface SessionData {
  sessionID: string
  toolCalls: ToolCall[]
  messages: Message[]
  startedAt: string
  lastObsidianWriteAt: string | null  // updated when any Obsidian tool fires (Option B)
}

interface NoteLoggerConfig {
  model: string | null
  base_url: string | null
  api_key: string | null
  vault: string | null
  note_skill: string
  min_tool_calls: number
  min_messages: number
  log_path: string
  log_enabled: boolean
  toast_enabled: boolean
  os_notify: boolean
}

// ── Config loader ──────────────────────────────────────────────────────────
// OpenCode does NOT pass plugin tuple options to local file plugins (options arg is always {}).
// Read config directly from opencode.json in the project directory instead.

function readPluginConfig(configPath: string): Partial<NoteLoggerConfig> {
  try {
    const json = JSON.parse(readFileSync(configPath, "utf8"))
    const plugins: unknown[] = json.plugin ?? []
    for (const entry of plugins) {
      if (Array.isArray(entry) && entry.length >= 2) {
        const pluginOptions = entry[1] as Record<string, unknown>
        if (pluginOptions.obsidian_note_logger) {
          return pluginOptions.obsidian_note_logger as Partial<NoteLoggerConfig>
        }
      }
    }
  } catch {
    // No config file or parse error — return empty
  }
  return {}
}

function loadConfig(directory: string, worktree: string): NoteLoggerConfig {
  // Read global config first (base layer), then project-level config (overrides).
  // This mirrors OpenCode's own config merge behaviour: global → project.
  // When the plugin is installed globally, `directory` = ~/.config/opencode/
  // and `worktree` = the current project repo. The project opencode.json may
  // only set `project` and `vault`, inheriting everything else from global.
  const globalRaw = readPluginConfig(resolve(directory, "opencode.json"))
  const projectRaw = worktree !== directory
    ? readPluginConfig(resolve(worktree, "opencode.json"))
    : {}
  // Merge: project-level values override global, but only if explicitly set (not null/undefined)
  const raw: Partial<NoteLoggerConfig> = { ...globalRaw }
  for (const [k, v] of Object.entries(projectRaw)) {
    if (v !== null && v !== undefined) {
      (raw as Record<string, unknown>)[k] = v
    }
  }
  return {
    model: raw.model ?? null,
    base_url: raw.base_url ?? null,
    api_key: raw.api_key ?? null,
    vault: raw.vault ?? null,
    note_skill: raw.note_skill ?? "obsidian-dev-notes",
    min_tool_calls: raw.min_tool_calls ?? 2,
    min_messages: raw.min_messages ?? 3,
    log_path: raw.log_path ?? "wiki/log.md",
    log_enabled: raw.log_enabled ?? true,
    toast_enabled: raw.toast_enabled ?? true,
    os_notify: raw.os_notify ?? false,
  }
}

// ── Session helpers ────────────────────────────────────────────────────────

function getOrCreate(sessions: Map<string, SessionData>, sid: string): SessionData {
  if (!sessions.has(sid)) {
    sessions.set(sid, {
      sessionID: sid,
      toolCalls: [],
      messages: [],
      startedAt: new Date().toISOString(),
      lastObsidianWriteAt: null,
    })
  }
  return sessions.get(sid)!
}

// ── Plugin export ──────────────────────────────────────────────────────────
// Named export — matches the pattern all working OpenCode plugins use.
// Config is read directly from opencode.json because OpenCode does NOT pass
// plugin tuple options to local file plugins (options arg is always {}).

export const ObsidianNoteLoggerPlugin = async (
  { client, worktree, directory, $ }: PluginInput,
) => {
  const config = loadConfig(directory, worktree)
  const sessions = new Map<string, SessionData>()
  // Bug fix: prevent same session from re-firing after it's been processed.
  // Without this, message.updated events after sessions.delete() re-create the
  // session entry via getOrCreate(), causing duplicate note writes on subsequent idle events.
  const processedSessions = new Set<string>()
  const SCRIPT = resolve(import.meta.dir, "../tools/obsidian_note_writer.py")

  // Obsidian tool names — actual registered names have obsidian_ prefix
  // Bug fix: was using bare names (createNote) but registry uses obsidian_createNote
  const OBSIDIAN_TOOLS = new Set([
    "obsidian_createNote", "obsidian_readNote", "obsidian_appendToNote", "obsidian_deleteNote",
    "obsidian_listFiles", "obsidian_setProperty", "obsidian_readProperty", "obsidian_removeProperty",
    "obsidian_listProperties", "obsidian_listTags", "obsidian_listTasks", "obsidian_toggleTask",
    "obsidian_getBacklinks", "obsidian_getOrphans", "obsidian_readDailyNote", "obsidian_appendToDailyNote",
    "obsidian_evalJs",
  ])

  await client.app.log({
    body: {
      service: "obsidian-note-logger",
      level: "info",
      message: `obsidian_note_logger loaded — vault=${config.vault} min_tools=${config.min_tool_calls} min_msgs=${config.min_messages}`,
    },
  })

  // ── tool.execute.after — track tool calls per session ──────────────────
  // Signature: (input: {tool, sessionID, callID, args}, output: {title, output, metadata})

  const handleToolAfter = async (
    input: { tool: string; sessionID: string; callID: string; args: any },
    output: { title: string; output: string; metadata: any },
  ) => {
    const sid = input.sessionID
    if (!sid) return
    // Don't re-create session data for already-processed sessions
    if (processedSessions.has(sid)) return
    const s = getOrCreate(sessions, sid)
    const toolName = input.tool ?? "unknown"
    const now = new Date().toISOString()
    s.toolCalls.push({
      tool: toolName,
      input: input.args ?? {},
      output: output.output ?? "",
      timestamp: now,
    })
    // Delta capture: track last Obsidian vault touch (Option B)
    if (OBSIDIAN_TOOLS.has(toolName)) {
      s.lastObsidianWriteAt = now
    }
  }

  // ── Trigger Python worker when session goes idle ───────────────────────

  const handleSessionIdle = async (sid: string) => {
    if (!sid) return
    // Guard: never re-process a session that already completed (success or skip)
    if (processedSessions.has(sid)) return
    const s = sessions.get(sid)
    if (!s) return

    // Gate: threshold check
    if (s.toolCalls.length < config.min_tool_calls) return
    if (s.messages.length < config.min_messages) return

    const transcriptPath = `${tmpdir()}/opencode-session-${sid}.json`
    const configPath = `${tmpdir()}/opencode-config-${sid}.json`

    // Outer try/finally guarantees sessions.delete(sid) always runs
    try {
      try {
        writeFileSync(transcriptPath, JSON.stringify(s, null, 2))
        writeFileSync(configPath, JSON.stringify(config, null, 2))
      } catch (err: any) {
        await client.app.log({
          body: {
            service: "obsidian-note-logger",
            level: "error",
            message: `Failed to write IPC files: ${err.message}`,
          },
        })
        return
      }

      try {
        const opencodeJsonPath = resolve(directory, "opencode.json")
      const proc = await $`python3 ${SCRIPT} ${transcriptPath} ${configPath} ${worktree} ${opencodeJsonPath}`.nothrow()
        const stdout = proc.stdout.toString().trim()
        const stderr = proc.stderr.toString().trim()

        if (proc.exitCode !== 0) {
          throw new Error(`exit ${proc.exitCode}: ${stderr || stdout}`)
        }

        const parsed = JSON.parse(stdout)

        if (parsed.status === "written" && config.toast_enabled) {
          const paths: string[] = parsed.paths ?? (parsed.path ? [parsed.path] : [])
          const label = paths.length === 1
            ? `Note written: ${paths[0]}`
            : `${paths.length} notes written to Obsidian`
          await client.tui.showToast({
            body: { message: label, variant: "success" },
          })
        }
        // "skipped" status: no toast per spec

        // Only lock the session out on success/skip — errors stay retryable.
        // If we added to processedSessions on error, a transient LLM failure
        // would permanently block this session from ever being captured.
        processedSessions.add(sid)
      } catch (err: any) {
        await client.app.log({
          body: {
            service: "obsidian-note-logger",
            level: "error",
            message: `Note writer failed: ${err.message}`,
          },
        })
        if (config.toast_enabled) {
          await client.tui.showToast({
            body: { message: "Obsidian note failed — will retry on next idle", variant: "error" },
          })
        }
        try { unlinkSync(transcriptPath) } catch {}
        try { unlinkSync(configPath) } catch {}
        // Do NOT add to processedSessions — next idle can retry after user sends a message
      }
    } finally {
      // Always clean up in-memory session data regardless of outcome
      sessions.delete(sid)
    }
  }

  return {
    // ── tool.execute.after — correct two-argument signature ──────────────
    "tool.execute.after": handleToolAfter,

    // ── event — single generic handler dispatching by event.type ─────────
    // Replaces the invalid "message.updated", "session.idle", "session.deleted" keys.
    // All SDK events arrive here; we only act on the three we care about.
    "event": async ({ event }: { event: any }) => {
      const type = event?.type
      const props = event?.properties ?? {}

      // Diagnostic: log every event type so we can confirm the hook fires
      await client.app.log({
        body: { service: "obsidian-note-logger", level: "debug", message: `event: ${type}` },
      })

      if (type === "message.updated") {
        // props.info is a Message (UserMessage | AssistantMessage)
        const msg = props.info
        if (!msg) return
        const sid = msg.sessionID
        if (!sid) return
        // Don't re-create session data for already-processed sessions
        if (processedSessions.has(sid)) return
        const s = getOrCreate(sessions, sid)
        const msgID = msg.id ?? `msg-${Date.now()}`

        // Extract text content from parts (AssistantMessage) or text (UserMessage)
        let content = ""
        if (Array.isArray(msg.parts)) {
          content = msg.parts
            .filter((p: any) => p.type === "text")
            .map((p: any) => p.text ?? "")
            .join("")
        } else if (typeof msg.text === "string") {
          content = msg.text
        }
        const role = msg.role ?? "assistant"

        // Upsert by message ID (handles streaming — last write wins)
        const existing = s.messages.findIndex((m) => m.id === msgID)
        if (existing >= 0) {
          s.messages[existing] = { id: msgID, role, content, timestamp: new Date().toISOString() }
        } else {
          s.messages.push({ id: msgID, role, content, timestamp: new Date().toISOString() })
        }
      }

      else if (type === "session.idle") {
        // props.sessionID
        const sid = props.sessionID
        await handleSessionIdle(sid)
      }

      else if (type === "session.deleted") {
        // props.info is a Session object with id field
        const sid = props.info?.id ?? props.sessionID
        if (sid) sessions.delete(sid)
      }
    },
  }
}
