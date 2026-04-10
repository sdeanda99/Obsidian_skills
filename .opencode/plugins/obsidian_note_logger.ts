import type { PluginInput } from "@opencode-ai/plugin"
import { resolve } from "path"
import { writeFileSync, unlinkSync } from "fs"
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

function loadConfig(project: Record<string, unknown>): NoteLoggerConfig {
  const raw = (project["obsidian_note_logger"] ?? {}) as Partial<NoteLoggerConfig>
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

export default async function ({ project, client, worktree, $ }: PluginInput) {
  const config = loadConfig(project)
  const sessions = new Map<string, SessionData>()
  const SCRIPT = resolve(import.meta.dir, "../tools/obsidian_note_writer.py")

  // Obsidian tool names — any of these firing updates lastObsidianWriteAt (Option B)
  const OBSIDIAN_TOOLS = new Set([
    "createNote", "readNote", "appendToNote", "deleteNote", "listFiles",
    "setProperty", "readProperty", "removeProperty", "listProperties",
    "listTags", "listTasks", "toggleTask", "getBacklinks", "getOrphans",
    "readDailyNote", "appendToDailyNote", "evalJs",
  ])

  await client.app.log({
    body: {
      service: "obsidian-note-logger",
      level: "info",
      message: "obsidian_note_logger loaded — watching sessions for Decisions and Patterns",
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
        const result = await $`python3 ${SCRIPT} ${transcriptPath} ${configPath} ${worktree}`.text()
        const parsed = JSON.parse(result.trim())

        if (parsed.status === "written" && config.toast_enabled) {
          await client.tui.showToast({
            body: { message: `Note written: ${parsed.path}`, variant: "success" },
          })
        }
        // "skipped" status: no toast per spec
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
            body: { message: "Obsidian note failed — check wiki/log.md", variant: "error" },
          })
        }
        try { unlinkSync(transcriptPath) } catch {}
        try { unlinkSync(configPath) } catch {}
      }
    } finally {
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

      if (type === "message.updated") {
        // props.info is a Message (UserMessage | AssistantMessage)
        const msg = props.info
        if (!msg) return
        const sid = msg.sessionID
        if (!sid) return
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
