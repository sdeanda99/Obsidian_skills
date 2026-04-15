# obsidian_note_logger

Autonomous OpenCode plugin that captures Decisions, Patterns, Learnings, and Problem-Solutions from your development sessions directly into Obsidian — zero manual effort required.

After every substantive OpenCode session, the plugin fires two LLM classification passes over your session history and writes structured, cross-linked notes to your vault following the `obsidian-dev-notes` schema.

---

## How It Works

1. **Accumulate** — the plugin records every tool call and message during the session
2. **Threshold check** — on `session.idle`, filters sessions below `min_tool_calls` / `min_messages`
3. **Path A** — full session transcript sent to LLM → identifies all distinct decisions, patterns, and learnings (no cap on count)
4. **Path B** — session timeline scanned for error→fix reasoning arcs → each arc classified as a problem-solution note
5. **Generate** — each classification produces a structured Obsidian note with git commit references from the session
6. **Write** — notes written to vault (`Decisions/`, `Patterns/`, `Learnings/`), wikilinks inserted into the project MOC
7. **Notify** — TUI toast + audit log entry in `wiki/log.md`

### Skills & Agents

| Name | Trigger | What it does |
|---|---|---|
| `init-new-moc` | "new project", "init project", "create MOC" | Guided setup wizard — install level, provider, config, MOC creation, verification |
| `@notedrift` | "realign my notes", "update MOC", "note drift" | Realigns project MOC, enriches cross-links between notes |
| `obsidian-dev-notes` | "document this decision", "capture this pattern" | Note structure and vault management |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| [Obsidian](https://obsidian.md/) 1.12+ | Desktop app, installer version |
| Obsidian CLI | Enable: Settings → General → Command line interface → toggle on |
| [Omnisearch plugin](https://github.com/scambier/obsidian-omnisearch) | Enable HTTP Server in Omnisearch settings (port 51361) |
| Python 3.10+ | For the note writer worker |
| `openai>=1.0.0` | `pip install openai>=1.0.0` |
| Bun | For running TypeScript tools |
| Ollama (optional) | For local inference — `ollama serve` |

---

## Installation

### Option A: Project-level (recommended for first setup)

Plugin config lives in your project's `opencode.json`. Each project has its own vault and model settings.

```bash
git clone https://github.com/sdeanda99/Obsidian_skills.git
cd Obsidian_skills
pip install openai>=1.0.0
```

Then run `init-new-moc` from any OpenCode session in your project:

```
"new project"   or   "init project"   or   "create MOC"
```

The wizard handles everything else.

### Option B: Global install

Plugin available in all repos on your machine. Each project adds a minimal `opencode.json` override with just `project` and optionally `vault`.

```bash
git clone https://github.com/sdeanda99/Obsidian_skills.git
cd Obsidian_skills

# Copy plugin files to global OpenCode config
mkdir -p ~/.config/opencode/plugins \
          ~/.config/opencode/tools \
          ~/.config/opencode/tools/Modelfiles \
          ~/.config/opencode/agents

cp .opencode/plugins/obsidian_note_logger.ts ~/.config/opencode/plugins/
cp .opencode/tools/obsidian_note_writer.py   ~/.config/opencode/tools/
cp .opencode/tools/Modelfiles/*.Modelfile    ~/.config/opencode/tools/Modelfiles/
cp .opencode/agents/notedrift.md             ~/.config/opencode/agents/
cp -r .opencode/skills/                      ~/.config/opencode/skills/

pip install openai>=1.0.0
```

Then run `init-new-moc` — choose **Global** when prompted for install level.

**Per-project override** (in each new project's `opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [[
    "~/.config/opencode/plugins/obsidian_note_logger.ts",
    {
      "obsidian_note_logger": {
        "project": "your-project-slug",
        "vault": "YourVault"
      }
    }
  ]]
}
```

Or just run `init-new-moc` in each new project repo — it creates this file for you.

---

## First-Time Setup

Run from any OpenCode session:

```
"new project"
```

The `init-new-moc` wizard walks you through:

1. **Install level** — project-level or global
2. **Project identity** — name → kebab slug, vault name, one-sentence overview, domain tags
3. **Inference provider** — OpenRouter (cloud) or Ollama (local)
4. **Thresholds** — `min_tool_calls`, `min_messages`
5. **Notifications** — toasts, OS notify, audit log
6. **Verification** — vault, Omnisearch, Ollama models, OpenRouter key, Modelfile context sync
7. **MOC creation** — writes `Projects/<ProjectName>-MOC.md` to Obsidian
8. **Config write** — previews changes, writes `opencode.json` atomically on confirm

---

## Inference Providers

### OpenRouter (cloud)

Uses your OpenRouter API key automatically from `~/.local/share/opencode/auth.json`.

```json
{
  "obsidian_note_logger": {
    "base_url": "https://openrouter.ai/api/v1/",
    "api_key": null,
    "model": "anthropic/claude-haiku-4-5",
    "ollama_model": null
  }
}
```

Set up your key: run `/connect` in the OpenCode TUI and select OpenRouter.

### Ollama (local — fully private, no API costs)

Requires Ollama running with the custom `notetaker` and `note-drift` models.

**1. Pull the base model:**
```bash
ollama pull nemotron-cascade-2:latest
```

**2. Create custom models from Modelfiles:**
```bash
ollama create notetaker   -f .opencode/tools/Modelfiles/notetaker.Modelfile
ollama create note-drift  -f .opencode/tools/Modelfiles/notedrift.Modelfile
```

Both models use **250K context window** and are tuned for structured JSON classification.

**3. Configure:**
```json
{
  "obsidian_note_logger": {
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "model": "notetaker",
    "ollama_model": "notetaker"
  }
}
```

---

## Full Config Reference

```jsonc
{
  "obsidian_note_logger": {

    // Project identity
    // null = pipeline bails cleanly with prompt to run init-new-moc
    "project": null,           // kebab-case slug matching your MOC filename prefix
    "vault": null,             // Obsidian vault directory name

    // LLM inference — configure via init-new-moc or manually
    "model": null,             // null = auto-detect from provider
    "base_url": null,          // null = OpenRouter; "http://localhost:11434/v1" = Ollama
    "api_key": null,           // null = auto-read from auth.json; "ollama" for local
    "ollama_model": null,      // Ollama model alias (used when base_url = localhost:11434)

    // Note style
    "note_skill": "obsidian-dev-notes",  // skill defining note structure and schema

    // Session thresholds — sessions below these are silently ignored
    "min_tool_calls": 10,      // minimum tool calls before pipeline fires
    "min_messages": 8,         // minimum messages before pipeline fires

    // Audit log
    "log_enabled": true,       // write entry to vault after each note written
    "log_path": "wiki/log.md", // vault-relative path for audit log

    // Notifications
    "toast_enabled": true,     // TUI toast on note written / error
    "os_notify": true          // OS desktop notification after note written
  }
}
```

---

## Agents

### `@notedrift`

Realigns your project MOC and enriches cross-links between related notes.

**Invoke:** say "realign my notes", "update MOC", or "fix note drift"

**What it does:**
- Adds missing wikilinks to the project MOC under correct headings
- Enriches cross-links between the top 5 most related note pairs
- Updates the MOC `updated` frontmatter date
- May rewrite the MOC Overview if clearly outdated

**What it does NOT do:** create new notes, delete anything, rewrite entire note bodies

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `project not configured — run init-new-moc` | Run `init-new-moc` skill to set the project slug |
| Notes writing to wrong MOC | Check `project` field in `opencode.json` matches your MOC filename prefix |
| Pipeline never fires | Lower `min_tool_calls`/`min_messages`, or check `wiki/log.md` for skipped entries |
| `LLM classification failed` | Check Ollama is running (`ollama serve`) or OpenRouter key is set |
| `notetaker` model not found | Run `ollama create notetaker -f .opencode/tools/Modelfiles/notetaker.Modelfile` |
| Omnisearch unavailable | Enable HTTP Server in Obsidian → Settings → Omnisearch |
| MOC insert always fails | Confirm `project` slug matches the MOC filename (e.g. `my-project` → `Projects/MyProject-MOC.md`) |
| Notes not appearing in Obsidian | Check `vault` field matches your vault directory name exactly |

---

## Repository Structure

```
.opencode/
├── plugins/
│   └── obsidian_note_logger.ts     # OpenCode plugin — session accumulator, idle trigger
├── tools/
│   ├── obsidian_note_writer.py     # Python worker — classification, generation, vault write
│   └── Modelfiles/
│       ├── notetaker.Modelfile     # nemotron-cascade-2, 250K ctx, temp=0
│       └── notedrift.Modelfile     # nemotron-cascade-2, 250K ctx, temp=0.2
├── agents/
│   └── notedrift.md                # @notedrift subagent definition
└── skills/
    ├── init-new-moc/               # Setup wizard skill
    ├── notedrift/                  # NoteDrift invocation skill
    └── obsidian-dev-notes/         # Note structure and vault management skill

tools/
├── obsidian.ts                     # OpenCode custom tool — vault CRUD (17 exports)
└── omnisearch.ts                   # OpenCode custom tool — fuzzy vault search

obsidian-cli/                       # Skill: general-purpose vault management
obsidian-dev-notes/                 # Skill: structured developer knowledge
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

**Author:** Sebastian De Anda
**Repository:** https://github.com/sdeanda99/Obsidian_skills
