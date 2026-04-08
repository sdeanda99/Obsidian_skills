import { tool } from "@opencode-ai/plugin"

// --- Interfaces ---

interface ObsidianTag {
  name: string
  count?: number
}

interface ObsidianTask {
  path?: string
  line?: number
  content: string
  status: string
}

interface ObsidianBacklink {
  path: string
  count?: number
}

interface ObsidianProperty {
  name: string
  value: unknown
  type?: string
}

// --- Helpers ---

function buildArgs(
  vault: string | undefined,
  command: string,
  params: Record<string, string | boolean | number | undefined>
): string[] {
  const args: string[] = ["obsidian"]
  if (vault) args.push(`vault=${vault}`)
  args.push(command)
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === false) continue
    if (val === true) {
      args.push(key)
    } else {
      const encoded = String(val).replace(/\n/g, "\\n").replace(/\t/g, "\\t")
      args.push(`${key}=${encoded}`)
    }
  }
  return args
}

function handleError(error: unknown): string {
  const err = error as Error
  if (err.message.includes("command not found") || err.message.includes("not found")) {
    return JSON.stringify({
      error: "Obsidian CLI not found",
      details: "Enable CLI in Obsidian: Settings → General → Command line interface. Restart your terminal after registration.",
    }, null, 2)
  }
  if (
    err.message.includes("No vault") ||
    err.message.includes("Cannot connect") ||
    err.message.includes("ECONNREFUSED")
  ) {
    return JSON.stringify({
      error: "Cannot connect to Obsidian",
      details: "Open Obsidian and ensure a vault is active, or pass vault=<name> to target a specific vault.",
    }, null, 2)
  }
  return JSON.stringify({ error: "CLI command failed", message: err.message }, null, 2)
}

async function run(args: string[]): Promise<string> {
  return (await Bun.$`${args}`.text()).trim()
}

// --- Note Tools ---

export const createNote = tool({
  description: "Create or overwrite a note in the Obsidian vault. Provide name (wikilink-style) or path (full vault path). Use appendToNote for adding to existing notes. Set overwrite: true to replace existing content.",
  args: {
    name: tool.schema.string().optional().describe("File name without path or extension"),
    path: tool.schema.string().optional().describe("Full path from vault root, e.g. Projects/MyMOC.md"),
    content: tool.schema.string().optional().describe("Note content. Actual newlines are encoded automatically."),
    template: tool.schema.string().optional().describe("Obsidian template name to apply (requires Templates plugin)"),
    overwrite: tool.schema.boolean().default(false).describe("Overwrite existing file. Default: false"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, path, content, template, overwrite, vault } = args
    try {
      const output = await run(buildArgs(vault, "create", { name, path, content, template, overwrite }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const readNote = tool({
  description: "Read the full markdown content of a note. Use before modifying a note (read-modify-overwrite pattern for heading-targeted inserts). Defaults to the active file.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "read", { file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const appendToNote = tool({
  description: "Append content to the end of a note. For inserting under a specific heading, use the read-modify-overwrite pattern with readNote + createNote instead.",
  args: {
    content: tool.schema.string().describe("Content to append. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    inline: tool.schema.boolean().optional().describe("Append without prepending a newline"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { content, file, path, inline, vault } = args
    try {
      const output = await run(buildArgs(vault, "append", { content, file, path, inline }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const deleteNote = tool({
  description: "Delete a note. Moves to system trash by default. Pass permanent: true to skip trash.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    permanent: tool.schema.boolean().optional().describe("Skip trash, delete permanently"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, permanent, vault } = args
    try {
      const output = await run(buildArgs(vault, "delete", { file, path, permanent }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Files & Folders ---

export const listFiles = tool({
  description: "List notes in the vault or a specific folder. Returns file paths. Use to browse vault structure or find notes in a folder (e.g. listFiles({ folder: 'Inbox' })).",
  args: {
    folder: tool.schema.string().optional().describe("Folder path relative to vault root. Omit to list all files."),
    ext: tool.schema.string().optional().describe("Filter by extension, e.g. 'md'"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { folder, ext, vault } = args
    try {
      const output = await run(buildArgs(vault, "files", { folder, ext }))
      const files = output.split("\n").filter(Boolean)
      return JSON.stringify({ files }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Properties ---

export const setProperty = tool({
  description: "Set a frontmatter property on a note. Use to update fields like status, updated date, or tags. Specify type for new properties (defaults to text if omitted).",
  args: {
    name: tool.schema.string().describe("Property name (frontmatter key). Required."),
    value: tool.schema.string().describe("Property value. Required."),
    type: tool.schema.string().optional().describe("Property type: text | list | number | checkbox | date | datetime"),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, value, type, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:set", { name, value, type, file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const readProperty = tool({
  description: "Read the value of a single frontmatter property from a note.",
  args: {
    name: tool.schema.string().describe("Property name. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:read", { name, file, path }))
      return JSON.stringify({ name, value: output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const removeProperty = tool({
  description: "Remove a frontmatter property from a note.",
  args: {
    name: tool.schema.string().describe("Property name to remove. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { name, file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "property:remove", { name, file, path }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const listProperties = tool({
  description: "List all frontmatter properties on a note. Returns property names, values, and types.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "properties", { file, path, format: "json" }))
      const properties: ObsidianProperty[] = JSON.parse(output)
      return JSON.stringify({ properties }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Tags ---

export const listTags = tool({
  description: "List tags in the vault or on a specific note. Returns tag names and optional counts. Use for vault-wide tag queries or to inspect a note's tags.",
  args: {
    file: tool.schema.string().optional().describe("File name. Omit to query vault-wide."),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    sort: tool.schema.string().optional().describe("Sort by 'count' (frequency) or omit for alphabetical"),
    counts: tool.schema.boolean().optional().describe("Include occurrence counts in results"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, sort, counts, vault } = args
    try {
      const output = await run(buildArgs(vault, "tags", { file, path, sort, counts, format: "json" }))
      const tags: ObsidianTag[] = JSON.parse(output)
      return JSON.stringify({ tags }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Tasks ---

export const listTasks = tool({
  description: "List tasks in a file or across the vault. Filter by status. Use verbose for file paths and line numbers. Use for project health checks and weekly reviews.",
  args: {
    file: tool.schema.string().optional().describe("File name. Omit to query vault-wide."),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    done: tool.schema.boolean().optional().describe("Show only completed tasks"),
    todo: tool.schema.boolean().optional().describe("Show only incomplete tasks"),
    verbose: tool.schema.boolean().optional().describe("Group by file with line numbers (needed for toggleTask)"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, done, todo, verbose, vault } = args
    try {
      const output = await run(buildArgs(vault, "tasks", { file, path, done, todo, verbose, format: "json" }))
      const tasks: ObsidianTask[] = JSON.parse(output)
      return JSON.stringify({ tasks }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const toggleTask = tool({
  description: "Toggle or set the completion status of a specific task by file and line number. Use listTasks with verbose: true first to find line numbers.",
  args: {
    line: tool.schema.number().int().positive().describe("Line number of the task. Required."),
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    done: tool.schema.boolean().optional().describe("Mark as done [x]"),
    todo: tool.schema.boolean().optional().describe("Mark as todo [ ]"),
    toggle: tool.schema.boolean().optional().describe("Toggle current status"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { line, file, path, done, todo, toggle, vault } = args
    try {
      const output = await run(buildArgs(vault, "task", { line, file, path, done, todo, toggle }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Links ---

export const getBacklinks = tool({
  description: "List files that link to a given note. Use during weekly review to verify a note is well-connected, or before archiving a project to confirm the MOC is reachable.",
  args: {
    file: tool.schema.string().optional().describe("File name for wikilink-style resolution"),
    path: tool.schema.string().optional().describe("Full path from vault root"),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { file, path, vault } = args
    try {
      const output = await run(buildArgs(vault, "backlinks", { file, path, format: "json" }))
      const backlinks: ObsidianBacklink[] = JSON.parse(output)
      return JSON.stringify({ backlinks }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const getOrphans = tool({
  description: "List notes with no incoming links. Use during weekly review to find disconnected notes that need to be connected to a MOC or processed from Inbox.",
  args: {
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { vault } = args
    try {
      const output = await run(buildArgs(vault, "orphans", {}))
      const orphans = output.split("\n").filter(Boolean)
      return JSON.stringify({ orphans }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Daily Notes ---

export const readDailyNote = tool({
  description: "Read today's daily note content. Use during weekly review to retrieve daily captures for processing into typed notes.",
  args: {
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { vault } = args
    try {
      const output = await run(buildArgs(vault, "daily:read", {}))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

export const appendToDailyNote = tool({
  description: "Append content to today's daily note. Use for quick captures — insights, tasks, ideas — to be processed into typed notes during weekly review.",
  args: {
    content: tool.schema.string().describe("Content to append. Required."),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { content, vault } = args
    try {
      const output = await run(buildArgs(vault, "daily:append", { content }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})

// --- Escape Hatch ---

export const evalJs = tool({
  description: "Run JavaScript in the Obsidian app context. Advanced escape hatch — use only when no other tool covers the need. Has full access to app.vault, app.metadataCache, etc. No sandbox or timeout applied. Returns raw eval output.",
  args: {
    code: tool.schema.string().describe("JavaScript to execute. Has access to the global `app` object. Required."),
    vault: tool.schema.string().optional().describe("Vault name. Defaults to active vault."),
  },
  async execute(args) {
    const { code, vault } = args
    try {
      const output = await run(buildArgs(vault, "eval", { code }))
      return JSON.stringify({ output }, null, 2)
    } catch (error) {
      return handleError(error)
    }
  },
})
