import type { PluginContext } from "@opencode-ai/plugin"
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

// ── Plugin export ──────────────────────────────────────────────────────────

export default async function ({ project, client, worktree }: PluginContext) {
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

  return {
    "tool.execute.after": async (event: any) => {
      const sid = event.sessionID
      if (!sid) return
      if (!sessions.has(sid)) {
        sessions.set(sid, {
          sessionID: sid,
          toolCalls: [],
          messages: [],
          startedAt: new Date().toISOString(),
          lastObsidianWriteAt: null,
        })
      }
      const s = sessions.get(sid)!
      const toolName = event.tool ?? "unknown"
      const now = new Date().toISOString()
      s.toolCalls.push({
        tool: toolName,
        input: event.input ?? {},
        output: event.output ?? "",
        timestamp: now,
      })
      // Delta capture: track last Obsidian vault touch (Option B)
      if (OBSIDIAN_TOOLS.has(toolName)) {
        s.lastObsidianWriteAt = now
      }
    },

    "message.updated": async (event: any) => {
      const sid = event.sessionID
      if (!sid) return
      if (!sessions.has(sid)) {
        sessions.set(sid, {
          sessionID: sid,
          toolCalls: [],
          messages: [],
          startedAt: new Date().toISOString(),
          lastObsidianWriteAt: null,
        })
      }
      const s = sessions.get(sid)!
      const msgID = event.messageID ?? event.id ?? `msg-${Date.now()}`
      const content = typeof event.content === "string"
        ? event.content
        : (event.content?.text ?? event.content?.value ?? "")
      const role = event.role ?? "assistant"
      // Upsert by message ID (handles streaming — last write wins)
      const existing = s.messages.findIndex((m) => m.id === msgID)
      if (existing >= 0) {
        s.messages[existing] = { id: msgID, role, content, timestamp: new Date().toISOString() }
      } else {
        s.messages.push({ id: msgID, role, content, timestamp: new Date().toISOString() })
      }
    },

    "session.deleted": async (event: any) => {
      const sid = event.sessionID
      if (sid) sessions.delete(sid)
    },
  }
}
