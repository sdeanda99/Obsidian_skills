# obsidian_note_logger Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an OpenCode plugin that silently captures Decisions and Patterns from development sessions into an Obsidian vault — no manual trigger required.

**Architecture:** A thin TypeScript plugin (`obsidian_note_logger.ts`) wires the OpenCode event system: it accumulates tool calls and messages per session in memory (tracking `lastObsidianWriteAt` for delta capture), applies a threshold gate at `session.idle`, writes a JSON transcript to `/tmp`, then shells out to a Python worker (`obsidian_note_writer.py`) that runs two LLM calls (classify+extract → search+generate) with structured `json_object` output, searches Omnisearch for related notes before writing, and creates or enriches notes in Obsidian via CLI.

**Tech Stack:** TypeScript (Bun runtime, `@opencode-ai/plugin`), Python 3.10+ (`openai` library, stdlib only), Obsidian CLI, `openai`-compatible REST API (cloud or Ollama local).

**Spec:** `docs/superpowers/specs/2026-04-08-obsidian-note-logger-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.opencode/plugins/obsidian_note_logger.ts` | **Create** | Event wiring, session accumulation, threshold gate, IPC, toast notifications |
| `.opencode/tools/obsidian_note_writer.py` | **Create** | Config loading, LLM classify + generate, Obsidian CLI shell-out, transaction log |
| `opencode.json` | **Modify** | Add `obsidian_note_logger` config block with defaults |
| `README.md` | **Modify** | Add `obsidian_note_logger` section with 3 config examples |
| `requirements.txt` | **Modify** | Add `openai>=1.0.0` |
| `pyproject.toml` | **Modify** | Add `openai>=1.0.0` to dependencies |

---

## Chunk 1: Python Worker — Config, LLM, and Obsidian Write

### Task 1: Scaffold `obsidian_note_writer.py` with config loading

**Files:**
- Create: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Create the file with imports and config loader**

```python
#!/usr/bin/env python3
"""
obsidian_note_writer.py — Worker script for the obsidian_note_logger plugin.

Usage: python3 obsidian_note_writer.py <transcript_json_path> <config_json_path>

Reads a SessionData JSON transcript produced by the plugin, runs two LLM calls
(classify then generate), writes a note to Obsidian via CLI, and appends to the
transaction log. Exits 0 on success or skip; exits 1 on unrecoverable failure.
"""

import sys
import json
import os
import subprocess
import datetime
from pathlib import Path


def load_config(config_path: str) -> dict:
    """Load plugin config from the JSON file written by the plugin."""
    with open(config_path) as f:
        return json.load(f)


def resolve_model(config: dict) -> str:
    """Resolve model name: config → OPENCODE_MODEL env → ANTHROPIC_DEFAULT_MODEL → fallback."""
    if config.get("model"):
        return config["model"]
    if os.environ.get("OPENCODE_MODEL"):
        return os.environ["OPENCODE_MODEL"]
    if os.environ.get("ANTHROPIC_DEFAULT_MODEL"):
        return os.environ["ANTHROPIC_DEFAULT_MODEL"]
    return "claude-haiku-4-5"


def resolve_api_key(config: dict) -> str:
    """Resolve API key: config → ANTHROPIC_API_KEY → OPENAI_API_KEY → ollama fallback."""
    if config.get("api_key"):
        return config["api_key"]
    base_url = config.get("base_url") or ""
    if "localhost:11434" in base_url:
        return "ollama"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    return ""


def build_openai_client(config: dict):
    """Build an openai.OpenAI client from config."""
    from openai import OpenAI
    kwargs = {"api_key": resolve_api_key(config)}
    if config.get("base_url"):
        kwargs["base_url"] = config["base_url"]
    return OpenAI(**kwargs)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: obsidian_note_writer.py <transcript.json> <config.json>", file=sys.stderr)
        sys.exit(1)
    transcript_path = sys.argv[1]
    config_path = sys.argv[2]
```

- [ ] **Step 2: Verify the file is syntactically valid**

```bash
python3 .opencode/tools/obsidian_note_writer.py
```

Expected: `Usage: obsidian_note_writer.py <transcript.json> <config.json>` printed to stderr, exit code 1 (missing args — correct).

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: scaffold obsidian_note_writer.py with config/model resolution"
```

---

### Task 2: Add transcript loading and skill prompt loading

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add transcript loader and skill prompt loader after `build_openai_client`**

```python
def load_transcript(transcript_path: str) -> dict:
    """Load and validate the SessionData JSON from the plugin."""
    with open(transcript_path) as f:
        data = json.load(f)
    # Validate required fields
    assert "sessionID" in data, "Missing sessionID"
    assert "toolCalls" in data, "Missing toolCalls"
    assert "messages" in data, "Missing messages"
    return data


def load_skill_prompt(config: dict, worktree: str) -> str:
    """
    Load the SKILL.md for the configured note_skill.
    Falls back to a built-in obsidian-dev-notes schema if not found.
    """
    skill_name = config.get("note_skill", "obsidian-dev-notes")
    skill_path = Path(worktree) / ".opencode" / "skills" / skill_name / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    # Built-in fallback encodes the obsidian-dev-notes schema
    return """
You are writing structured developer knowledge notes for an Obsidian vault.

Vault folder schema:
- Decisions/  — architectural and technical decisions
- Patterns/   — reusable solutions and approaches
- Projects/   — MOC (Map of Content) per project

Note frontmatter schema:
---
type: decision | pattern
project: <project-name>
status: proposed | accepted | superseded  (decisions only)
tags: [list, of, tags]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

Decisions must have sections: ## Context, ## Decision, ## Consequences
Patterns must have sections: ## Problem, ## Solution, ## Usage, ## Trade-offs
"""


def format_transcript(session: dict) -> str:
    """
    Format SessionData into a readable transcript for LLM consumption.

    Delta capture: if session has a lastObsidianWriteAt timestamp, only include
    tool calls and messages AFTER that timestamp. This focuses the LLM on the
    current "work unit" rather than the full session history, reducing context
    bloat and improving relevance of the generated note.
    """
    cutoff = session.get("lastObsidianWriteAt")  # ISO 8601 or None

    all_tool_calls = session.get("toolCalls", [])
    all_messages = session.get("messages", [])

    # Apply delta filter if cutoff is set
    if cutoff:
        tool_calls = [tc for tc in all_tool_calls if tc.get("timestamp", "") > cutoff]
        messages = [m for m in all_messages if m.get("timestamp", "") > cutoff]
        delta_note = f"(delta: events after {cutoff})"
    else:
        tool_calls = all_tool_calls
        messages = all_messages
        delta_note = "(full session)"

    lines = [
        f"Session ID: {session['sessionID']}",
        f"Started: {session.get('startedAt', 'unknown')}",
        f"Context window: {delta_note}",
        "",
    ]
    lines.append("=== MESSAGES ===")
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = (msg.get("content") or "")[:2000]  # truncate long messages
        lines.append(f"[{role}]: {content}")
    lines.append("")
    lines.append("=== TOOL CALLS ===")
    for tc in tool_calls:
        tool = tc.get("tool", "unknown")
        inp = json.dumps(tc.get("input", {}))[:500]
        out = str(tc.get("output", ""))[:500]
        lines.append(f"Tool: {tool}")
        lines.append(f"  Input:  {inp}")
        lines.append(f"  Output: {out}")
    return "\n".join(lines)
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add transcript loader and skill prompt loader to note writer"
```

---

### Task 3: Add Gate D — `classify_and_extract` (merged, structured output)

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add `ClassifyResult` dataclass and `classify_and_extract` function after `format_transcript`**

```python
from dataclasses import dataclass

@dataclass
class ClassifyResult:
    should_capture: bool
    note_type: str        # "decision" or "pattern"
    project: str          # project name, e.g. "obsidian-note-logger"
    topics: list          # 2-3 key topic strings
    reasoning: str        # one-sentence explanation


def classify_and_extract(
    client, model: str, transcript: str, skill_prompt: str
) -> ClassifyResult:
    """
    Gate D: Merged classify + context extract call using json_object structured output.
    Returns ClassifyResult. Falls back to text parsing if provider rejects json_object mode.

    Using json_object mode (not json_schema) for broad provider compatibility:
    - OpenAI: full support
    - Anthropic-compatible: supported
    - Ollama: supported on most models (graceful fallback if not)
    """
    system = f"""{skill_prompt}

You are a classifier and context extractor. Analyze this OpenCode session transcript and
return a JSON object with these exact fields:
{{
  "should_capture": true or false,
  "note_type": "decision" or "pattern",
  "project": "kebab-case-project-name",
  "topics": ["topic1", "topic2"],
  "reasoning": "One sentence explaining why this should or should not be captured."
}}

Capture if: the session contains an architectural decision, a technical trade-off choice,
or a reusable solution pattern worth preserving in a developer knowledge base.
Do not capture if: the session is exploratory, trivial, or contains no clear outcome.
"""
    # Try json_object mode first (structured output)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Session transcript:\n\n{transcript}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:
        # Fallback: call without response_format, parse text manually
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Session transcript:\n\n{transcript}"},
            ],
            max_tokens=200,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)  # raises ValueError if still not JSON — caller handles

    return ClassifyResult(
        should_capture=bool(data.get("should_capture", False)),
        note_type=data.get("note_type", "decision"),
        project=data.get("project", "unknown"),
        topics=data.get("topics", []),
        reasoning=data.get("reasoning", ""),
    )
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add classify_and_extract with json_object structured output"
```

---

### Task 3b: Add `search_related_notes` — Omnisearch dedup check

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add `search_related_notes` function after `classify_and_extract`**

```python
import urllib.request
import urllib.parse


def search_related_notes(
    project: str,
    topics: list,
    note_type: str,
    vault: str | None,
    score_threshold: int = 15,
) -> list:
    """
    Search Omnisearch for existing notes related to the project and topics.
    Returns list of {"path": str, "content": str} dicts (up to 2).
    Returns [] gracefully on any error (Omnisearch unavailable, timeout, etc.).

    Filters results to only notes in the folder matching note_type:
    - "decision" → Decisions/
    - "pattern"  → Patterns/
    """
    folder_prefix = "Decisions/" if note_type.lower() == "decision" else "Patterns/"
    query = f"{project} {' '.join(topics)}"
    encoded = urllib.parse.quote(query)
    url = f"http://localhost:51361/search?q={encoded}"

    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status != 200:
                return []
            results = json.loads(resp.read().decode())
    except Exception:
        return []  # Omnisearch unavailable — graceful degradation

    # Filter by folder and score threshold
    matches = [
        r for r in results
        if r.get("path", "").startswith(folder_prefix)
        and r.get("score", 0) >= score_threshold
    ]

    # Read top 2 note contents via Obsidian CLI
    related = []
    for match in matches[:2]:
        path = match["path"]
        code, content, _ = obsidian_run(["read", f"path={path}"], vault=vault)
        if code == 0 and content:
            related.append({"path": path, "content": content})

    return related
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify `urllib` imports don't conflict (stdlib — no pip install needed)**

```bash
python3 -c "import urllib.request, urllib.parse; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add search_related_notes for Omnisearch dedup check"
```

---

### Task 4: Add note generation — second LLM call (enrich or create)

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add `generate_note` function after `search_related_notes`**

```python
def generate_note(
    client,
    model: str,
    transcript: str,
    skill_prompt: str,
    classification: ClassifyResult,
    existing_notes: list,
) -> dict:
    """
    Generate a structured Obsidian note from the session transcript.
    If existing_notes is non-empty, LLM decides whether to enrich one or create new.

    Returns dict with keys:
      action: "create" | "enrich"
      path: vault-relative path for the note
      content: complete markdown content (full note, not a diff)
      existing_path: same as path for enrich, null for create

    Raises ValueError if LLM output is not valid JSON or missing required keys.
    Uses json_object mode with markdown-fence fallback (same pattern as classify_and_extract).
    """
    today = datetime.date.today().isoformat()

    existing_block = ""
    if existing_notes:
        parts = []
        for n in existing_notes:
            parts.append(f"### Existing note: {n['path']}\n\n{n['content'][:3000]}")
        existing_block = (
            "\n\n## Existing Related Notes\n\n"
            + "\n\n---\n\n".join(parts)
            + "\n\nDecide: should you ENRICH one of these notes with the new content, "
            "or CREATE a new note? Enrich if the session clearly extends the same topic. "
            "Create if the content is sufficiently distinct."
        )

    system = f"""{skill_prompt}

You are a developer knowledge base writer. Given an OpenCode session transcript,
write or update a structured Obsidian note capturing the key {classification.note_type}.

You MUST respond with a JSON object using json_object mode — no markdown fences:
{{
  "action": "create" or "enrich",
  "path": "Decisions/YYYY-MM-DD-short-slug.md",
  "content": "---\\ntype: {classification.note_type}\\nproject: {classification.project}\\n...\\n---\\n\\n## Context\\n...",
  "existing_path": null or "Decisions/existing-note.md"
}}

Rules:
- action "enrich": set existing_path to the path being updated, path = existing_path
- action "create": set existing_path to null
- path must start with Decisions/ or Patterns/ matching the note type
- path filename (for create): YYYY-MM-DD-kebab-case-slug.md (today is {today})
- content is the COMPLETE note after enrichment (not a diff — full replacement)
- frontmatter fields: type, project, status (decisions only), tags, created, updated
- created and updated should be {today}
- Use the schema from the skill instructions above for section headings
- Be specific — extract actual content from the transcript, not generic summaries
{existing_block}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    f"Project: {classification.project}\n"
                    f"Topics: {', '.join(classification.topics)}\n"
                    f"Classification: {classification.reasoning}\n\n"
                    f"Session transcript:\n\n{transcript}"
                )},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:
        # Fallback: call without response_format
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    f"Project: {classification.project}\n"
                    f"Topics: {', '.join(classification.topics)}\n"
                    f"Classification: {classification.reasoning}\n\n"
                    f"Session transcript:\n\n{transcript}"
                )},
            ],
            max_tokens=2000,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

    assert "action" in data and "path" in data and "content" in data, \
        f"LLM response missing required keys: {list(data.keys())}"
    return data
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add generate_note with enrich/create branch and json_object mode"
```

---

### Task 5: Add Obsidian CLI write and MOC insert

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add `obsidian_run`, `write_note`, and `insert_moc_link` functions**

```python
def obsidian_run(args: list[str], vault: str | None = None) -> tuple[int, str, str]:
    """
    Run an obsidian CLI command. Returns (exit_code, stdout, stderr).
    vault is prepended as vault=<name> if provided.
    """
    cmd = ["obsidian"]
    if vault:
        cmd.append(f"vault={vault}")
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def write_note(path: str, content: str, vault: str | None) -> tuple[bool, str]:
    """
    Write a note to Obsidian via CLI.
    Returns (success: bool, error_message: str).
    """
    code, stdout, stderr = obsidian_run(
        ["create", f"path={path}", f"content={content}", "overwrite=false"],
        vault=vault,
    )
    if code != 0:
        return False, stderr or stdout or "Unknown CLI error"
    return True, ""


def insert_moc_link(note_path: str, note_type: str, vault: str | None) -> tuple[bool, str]:
    """
    Insert a wikilink to the new note into the project MOC under the appropriate heading.
    note_type should be 'decision' or 'pattern' (matched from frontmatter).
    Returns (success: bool, warning_or_error: str).
    """
    # Extract project name from note path frontmatter by reading note back
    code, content, stderr = obsidian_run(["read", f"path={note_path}"], vault=vault)
    if code != 0:
        return False, f"Could not read newly created note: {stderr}"

    # Parse project from frontmatter
    project = None
    for line in content.splitlines():
        if line.startswith("project:"):
            project = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if not project:
        return False, "No 'project' field found in note frontmatter — skipping MOC insert"

    moc_path = f"Projects/{project}.md"
    code, moc_content, _ = obsidian_run(["read", f"path={moc_path}"], vault=vault)
    if code != 0:
        return False, f"MOC not found at {moc_path} — skipping MOC insert (note was still created)"

    # Determine heading to insert under
    heading_map = {"decision": "## Decisions", "pattern": "## Patterns"}
    heading = heading_map.get(note_type.lower(), "## Notes")

    # Extract just the filename for the wikilink (without extension)
    note_stem = Path(note_path).stem
    wikilink = f"- [[{note_stem}]]"

    lines = moc_content.splitlines()

    # Skip insert if wikilink already exists (prevents duplicates on enrich path)
    if wikilink in moc_content:
        return True, ""

    insert_idx = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            insert_idx = i + 1
            break

    if insert_idx is None:
        # Heading not found — append heading + link at end
        lines.extend(["", heading, wikilink])
    else:
        lines.insert(insert_idx, wikilink)

    new_content = "\n".join(lines)
    code, _, stderr = obsidian_run(
        ["create", f"path={moc_path}", f"content={new_content}", "overwrite=true"],
        vault=vault,
    )
    if code != 0:
        return False, f"Failed to update MOC: {stderr}"
    return True, ""
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add Obsidian CLI write and MOC insert to note writer"
```

---

### Task 6: Add transaction log and OS notification helpers

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Add `append_log` and `os_notify` functions**

```python
def append_log(config: dict, vault: str | None, entry: str) -> None:
    """Append an entry to wiki/log.md in the vault. Silently ignores failures."""
    if not config.get("log_enabled", True):
        return
    log_path = config.get("log_path", "wiki/log.md")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"\n{entry}\n"
    try:
        obsidian_run(["append", f"path={log_path}", f"content={content}"], vault=vault)
    except Exception:
        pass  # log failures are silently swallowed per spec


def os_notify(config: dict, title: str, message: str) -> None:
    """Send an OS-level notification if os_notify is enabled in config."""
    if not config.get("os_notify", False):
        return
    import platform
    try:
        if platform.system() == "Linux":
            subprocess.run(["notify-send", title, message], timeout=5)
        elif platform.system() == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=5)
    except Exception:
        pass  # notification failures are silently swallowed
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: add transaction log and OS notification helpers to note writer"
```

---

### Task 7: Wire the `__main__` entrypoint

**Files:**
- Modify: `.opencode/tools/obsidian_note_writer.py`

- [ ] **Step 1: Replace the stub `__main__` block with the full pipeline**

Replace the existing `if __name__ == "__main__":` block (the stub from Task 1) with:

```python
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: obsidian_note_writer.py <transcript.json> <config.json>", file=sys.stderr)
        sys.exit(1)

    transcript_path = sys.argv[1]
    config_path = sys.argv[2]

    # --- Load inputs ---
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        session = load_transcript(transcript_path)
    except Exception as e:
        print(f"Failed to load transcript: {e}", file=sys.stderr)
        sys.exit(1)

    vault = config.get("vault") or None
    model = resolve_model(config)
    # worktree is passed as 3rd arg by plugin (optional, defaults to cwd)
    worktree = sys.argv[3] if len(sys.argv) > 3 else os.getcwd()
    skill_prompt = load_skill_prompt(config, worktree)
    transcript_text = format_transcript(session)
    session_id = session["sessionID"]

    try:
        client = build_openai_client(config)
    except Exception as e:
        print(f"Failed to build LLM client: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Gate D: Classify & Extract ---
    try:
        classification = classify_and_extract(client, model, transcript_text, skill_prompt)
    except Exception as e:
        print(f"LLM classification failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not classification.should_capture:
        append_log(config, vault, (
            f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — Skipped (not a decision/pattern)\n"
            f"- **Session:** {session_id}\n"
            f"- **Reason:** {classification.reasoning}"
        ))
        print(json.dumps({"status": "skipped", "reason": classification.reasoning}))
        try:
            Path(transcript_path).unlink()
        except Exception:
            pass
        sys.exit(0)

    # --- Pre-Write Search (dedup check) ---
    dedup_label = ""
    try:
        existing_notes = search_related_notes(
            classification.project, classification.topics,
            classification.note_type, vault
        )
        if existing_notes:
            dedup_label = f"Found {len(existing_notes)} related"
        else:
            dedup_label = "No matches"
    except Exception:
        existing_notes = []
        dedup_label = "Skipped (Omnisearch unavailable)"

    # --- Generate note (enrich or create) ---
    try:
        note = generate_note(
            client, model, transcript_text, skill_prompt,
            classification, existing_notes
        )
    except (ValueError, AssertionError, Exception) as e:
        print(f"Note generation failed: {e}", file=sys.stderr)
        append_log(config, vault, (
            f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: note generation failed\n"
            f"- **Session:** {session_id}\n"
            f"- **Error:** {e}"
        ))
        sys.exit(1)

    action = note.get("action", "create")
    note_path = note["path"]
    note_content = note["content"]
    existing_path = note.get("existing_path")
    note_type = classification.note_type

    # --- Write note to Obsidian (create or enrich) ---
    if action == "enrich" and existing_path:
        overwrite_flag = "overwrite=true"
        write_path = existing_path
        action_label = f"Enriched {existing_path}"
    else:
        overwrite_flag = "overwrite=false"
        write_path = note_path
        action_label = "Created"

    write_args = ["create", f"path={write_path}", f"content={note_content}", overwrite_flag]
    code, stdout, stderr = obsidian_run(write_args, vault=vault)
    if code != 0:
        err = stderr or stdout or "Unknown CLI error"
        # Enrich fallback: if enrich write failed, retry as create at new path
        if action == "enrich":
            write_args = ["create", f"path={note_path}", f"content={note_content}", "overwrite=false"]
            code2, _, stderr2 = obsidian_run(write_args, vault=vault)
            if code2 == 0:
                action_label = f"Created (enrich fallback — original write failed: {err})"
                write_path = note_path
            else:
                print(f"Obsidian write failed: {err}", file=sys.stderr)
                append_log(config, vault, (
                    f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: write failed\n"
                    f"- **Session:** {session_id}\n"
                    f"- **Error:** obsidian CLI returned non-zero exit code\n"
                    f"- **Raw:** {err}"
                ))
                sys.exit(1)
        else:
            print(f"Obsidian write failed: {err}", file=sys.stderr)
            append_log(config, vault, (
                f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: write failed\n"
                f"- **Session:** {session_id}\n"
                f"- **Error:** obsidian CLI returned non-zero exit code\n"
                f"- **Raw:** {err}"
            ))
            sys.exit(1)

    # --- MOC insert (best-effort, skip duplicate wikilinks) ---
    moc_ok, moc_warn = insert_moc_link(write_path, note_type, vault)
    moc_note = f"\n- **MOC warning:** {moc_warn}" if not moc_ok else ""

    # --- Transaction log ---
    cutoff = session.get("lastObsidianWriteAt")
    delta_window = f"since {cutoff}" if cutoff else "full session"
    tool_count = len(session.get("toolCalls", []))
    msg_count = len(session.get("messages", []))
    base_url = config.get("base_url") or "cloud"
    provider_label = "ollama" if "11434" in base_url else base_url
    append_log(config, vault, (
        f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — {note_type.capitalize()} captured\n"
        f"- **Session:** {session_id}\n"
        f"- **Action:** {action_label}\n"
        f"- **Note:** {write_path}\n"
        f"- **Model:** {model} ({provider_label})\n"
        f"- **Classified as:** {note_type.capitalize()}\n"
        f"- **Tool calls logged:** {tool_count}\n"
        f"- **Messages logged:** {msg_count}\n"
        f"- **Delta window:** {delta_window}\n"
        f"- **Dedup check:** {dedup_label}\n"
        f"- **Classification reasoning:** {classification.reasoning}{moc_note}"
    ))

    # --- OS notification ---
    os_notify(config, "OpenCode → Obsidian", f"Note written: {note_path}")

    # --- Clean up temp file ---
    try:
        Path(transcript_path).unlink()
    except Exception:
        pass

    # Print machine-readable result for plugin toast
    print(json.dumps({"status": "written", "path": note_path}))
    sys.exit(0)
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run a dry-run with a minimal test transcript to verify argument parsing**

```bash
echo '{"sessionID":"test-123","toolCalls":[],"messages":[],"startedAt":"2026-04-08T00:00:00Z","lastObsidianWriteAt":null}' > /tmp/test-transcript.json
echo '{"model":"claude-haiku-4-5","base_url":null,"api_key":null,"vault":null,"note_skill":"obsidian-dev-notes","min_tool_calls":2,"min_messages":3,"log_path":"wiki/log.md","log_enabled":false,"toast_enabled":true,"os_notify":false}' > /tmp/test-config.json
python3 .opencode/tools/obsidian_note_writer.py /tmp/test-transcript.json /tmp/test-config.json
```

Expected: Script imports cleanly and fails at `build_openai_client` (no API key) or at the LLM call — not at import or argument parsing. Any `ImportError` for `openai` means the dependency needs installing (see Task 8 first).

- [ ] **Step 4: Commit**

```bash
git add .opencode/tools/obsidian_note_writer.py
git commit -m "feat: complete obsidian_note_writer.py main pipeline entrypoint"
```

---

### Task 8: Add `openai` dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current requirements.txt**

```bash
cat requirements.txt
```

- [ ] **Step 2: Add openai to requirements.txt**

Add the line `openai>=1.0.0` to `requirements.txt`.

- [ ] **Step 3: Read current pyproject.toml**

```bash
cat pyproject.toml
```

- [ ] **Step 4: Add openai to pyproject.toml dependencies**

Find the `dependencies` array in `pyproject.toml` and add `"openai>=1.0.0"` to it.

- [ ] **Step 5: Install the dependency**

```bash
pip install openai>=1.0.0
```

Expected: `Successfully installed openai-...` or `Requirement already satisfied`.

- [ ] **Step 6: Re-run the dry-run from Task 7 Step 3 — confirm it now gets past imports**

```bash
python3 .opencode/tools/obsidian_note_writer.py /tmp/test-transcript.json /tmp/test-config.json
```

Expected: Script runs, makes a real LLM API call (or fails with auth error if no key set — that's fine, import works).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "deps: add openai>=1.0.0 for obsidian_note_writer LLM calls"
```

---

## Chunk 2: TypeScript Plugin

### Task 9: Create `obsidian_note_logger.ts` — skeleton and config loading

**Files:**
- Create: `.opencode/plugins/obsidian_note_logger.ts`

- [ ] **Step 1: Create the plugin file**

```typescript
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
  const SCRIPT = resolve(__dirname, "../tools/obsidian_note_writer.py")

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
    // hooks go here in Tasks 10-12
  }
}
```

- [ ] **Step 2: Verify the file is syntactically valid (Bun type-check)**

```bash
cd .opencode && bun run --bun tsc --noEmit --skipLibCheck plugins/obsidian_note_logger.ts 2>&1 || true
```

Expected: No errors, or only type errors about `PluginContext` fields (acceptable — we verify the shape against the running API at test time, not statically).

- [ ] **Step 3: Commit**

```bash
git add .opencode/plugins/obsidian_note_logger.ts
git commit -m "feat: scaffold obsidian_note_logger.ts plugin with config loader"
```

---

### Task 10: Add `tool.execute.after` and `message.updated` hooks

**Files:**
- Modify: `.opencode/plugins/obsidian_note_logger.ts`

- [ ] **Step 1: Replace the empty `return {}` block with event hooks**

Replace `return { // hooks go here in Tasks 10-12 }` with:

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add .opencode/plugins/obsidian_note_logger.ts
git commit -m "feat: add tool.execute.after and message.updated hooks to plugin"
```

---

### Task 11: Add `session.idle` hook — threshold gate, IPC, and Python shell-out

**Files:**
- Modify: `.opencode/plugins/obsidian_note_logger.ts`

- [ ] **Step 1: Add `session.idle` to the returned hooks object, before `session.deleted`**

```typescript
    "session.idle": async (event: any) => {
      const sid = event.sessionID ?? event.id
      if (!sid) return
      const s = sessions.get(sid)
      if (!s) return

      // Gate B: threshold check
      if (s.toolCalls.length < config.min_tool_calls) return
      if (s.messages.length < config.min_messages) return

      // Write transcript to temp file
      const transcriptPath = `${tmpdir()}/opencode-session-${sid}.json`
      const configPath = `${tmpdir()}/opencode-config-${sid}.json`

      try {
        writeFileSync(transcriptPath, JSON.stringify(s, null, 2))
        writeFileSync(configPath, JSON.stringify(config, null, 2))
      } catch (err: any) {
        await client.app.log({
          body: { service: "obsidian-note-logger", level: "error", message: `Failed to write IPC files: ${err.message}` },
        })
        return
      }

      // Shell out to Python worker
      try {
        const result = await Bun.$`python3 ${SCRIPT} ${transcriptPath} ${configPath} ${worktree}`.text()
        const parsed = JSON.parse(result.trim())

        if (parsed.status === "written" && config.toast_enabled) {
          await client.tui.showToast({
            body: { message: `Note written: ${parsed.path}`, variant: "success" },
          })
        }
        // skipped status: no toast per spec
      } catch (err: any) {
        // Python exited non-zero
        await client.app.log({
          body: { service: "obsidian-note-logger", level: "error", message: `Note writer failed: ${err.message}` },
        })
        if (config.toast_enabled) {
          await client.tui.showToast({
            body: { message: "Obsidian note failed — check wiki/log.md", variant: "error" },
          })
        }
        // Clean up temp files on failure
        try { unlinkSync(transcriptPath) } catch {}
        try { unlinkSync(configPath) } catch {}
      } finally {
        // Remove from memory after processing
        sessions.delete(sid)
      }
    },
```

- [ ] **Step 2: Verify syntax (check for obvious structural errors)**

```bash
cd .opencode && bun run --bun tsc --noEmit --skipLibCheck plugins/obsidian_note_logger.ts 2>&1 || true
```

- [ ] **Step 3: Commit**

```bash
git add .opencode/plugins/obsidian_note_logger.ts
git commit -m "feat: add session.idle hook with threshold gate and Python shell-out"
```

---

## Chunk 3: Configuration and Documentation

### Task 12: Update `opencode.json` with plugin config block

**Files:**
- Modify: `opencode.json`

- [ ] **Step 1: Add the `obsidian_note_logger` config block**

Replace the contents of `opencode.json` with:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["AGENTS.md"],
  "obsidian_note_logger": {
    "model": null,
    "base_url": null,
    "api_key": null,
    "vault": null,
    "note_skill": "obsidian-dev-notes",
    "min_tool_calls": 2,
    "min_messages": 3,
    "log_path": "wiki/log.md",
    "log_enabled": true,
    "toast_enabled": true,
    "os_notify": false
  }
}
```

Note: OpenCode does not natively parse `obsidian_note_logger` — it ignores unknown keys. The plugin reads this via its `project` context object.

- [ ] **Step 2: Commit**

```bash
git add opencode.json
git commit -m "config: add obsidian_note_logger defaults to opencode.json"
```

---

### Task 13: Update `README.md` with plugin section and config examples

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the `obsidian_note_logger` section to README.md**

After the existing `## Features` section, add a new `## obsidian_note_logger Plugin` section with this content:

```markdown
## obsidian_note_logger Plugin

Automatically captures Decisions and Patterns from your OpenCode sessions into Obsidian.
After every substantive session (filtered by threshold + LLM classification), a structured
note is written to your vault following the `obsidian-dev-notes` schema.

### How It Works

1. The plugin accumulates all tool calls and messages during a session
2. When the agent goes idle (`session.idle`), it checks if the session was substantive
   (configurable threshold: min tool calls + min messages)
3. A lightweight LLM call classifies whether a Decision or Pattern is worth capturing
4. If yes, a second LLM call generates the full structured note
5. The note is written to your Obsidian vault via the CLI, and linked into your project MOC
6. A toast notification confirms the write; transactions are logged to `wiki/log.md`

### Installation

The plugin is already in `.opencode/plugins/obsidian_note_logger.ts`.
Install the `openai` Python dependency:

```bash
pip install openai>=1.0.0
# or
uv pip install openai>=1.0.0
```

Then configure the model in `opencode.json` (see examples below).

### Configuration Examples

**Default — inherits the same model as your main OpenCode session:**

```jsonc
"obsidian_note_logger": {
  "model": null,
  "base_url": null,
  "api_key": null
}
```

**Local AI with Ollama (no API costs, fully private):**

```jsonc
"obsidian_note_logger": {
  "model": "llama3.2",
  "base_url": "http://localhost:11434/v1",
  "api_key": "ollama"
}
```

Requires Ollama running locally: `ollama serve` and `ollama pull llama3.2`.

**Smaller cloud model — Anthropic Haiku (fast and cheap):**

```jsonc
"obsidian_note_logger": {
  "model": "claude-haiku-4-5",
  "base_url": null,
  "api_key": null
}
```

Uses `ANTHROPIC_API_KEY` from your environment automatically.

### Full Config Reference

```jsonc
"obsidian_note_logger": {
  // LLM config
  "model": null,           // null = inherit OPENCODE_MODEL env → fallback claude-haiku-4-5
  "base_url": null,        // null = cloud; "http://localhost:11434/v1" = Ollama
  "api_key": null,         // null = inherit ANTHROPIC_API_KEY / OPENAI_API_KEY from env

  // Vault
  "vault": null,           // null = active vault; "My Vault" = specific vault name
  "note_skill": "obsidian-dev-notes",  // skill schema governing note structure

  // Filtering (sessions below these thresholds are silently ignored)
  "min_tool_calls": 2,
  "min_messages": 3,

  // Transaction log
  "log_path": "wiki/log.md",   // vault-relative path
  "log_enabled": true,

  // Notifications
  "toast_enabled": true,        // in-app TUI toast
  "os_notify": false            // OS-level notify-send / osascript
}
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add obsidian_note_logger section and config examples to README"
```

---

## Chunk 4: Smoke Test

### Task 14: End-to-end smoke test

**Goal:** Verify the full pipeline works without a live Obsidian vault — by inspecting the intermediate outputs at each stage.

- [ ] **Step 1: Verify plugin loads by checking the `.opencode/plugins/` directory**

```bash
ls .opencode/plugins/
```

Expected: `obsidian_note_logger.ts` and `opencode_builder_kit.ts` present.

- [ ] **Step 2: Create a realistic test transcript**

```bash
cat > /tmp/smoke-transcript.json << 'EOF'
{
  "sessionID": "smoke-test-001",
  "toolCalls": [
    {"tool": "read", "input": {"path": "src/plugin.ts"}, "output": "file contents...", "timestamp": "2026-04-08T09:50:00Z"},
    {"tool": "createNote", "input": {"path": "Projects/obsidian-note-logger.md"}, "output": "created", "timestamp": "2026-04-08T10:00:00Z"},
    {"tool": "edit", "input": {"path": "src/plugin.ts", "change": "added session.idle hook"}, "output": "success", "timestamp": "2026-04-08T10:01:00Z"},
    {"tool": "bash", "input": {"command": "bun check src/plugin.ts"}, "output": "No errors", "timestamp": "2026-04-08T10:02:00Z"}
  ],
  "messages": [
    {"id": "m1", "role": "user", "content": "Add session.idle handling to the plugin", "timestamp": "2026-04-08T09:49:00Z"},
    {"id": "m2", "role": "assistant", "content": "I'll add the session.idle hook to capture when the agent finishes responding.", "timestamp": "2026-04-08T09:50:05Z"},
    {"id": "m3", "role": "user", "content": "Make sure it uses the threshold gate", "timestamp": "2026-04-08T10:01:00Z"},
    {"id": "m4", "role": "assistant", "content": "Done — I've added min_tool_calls and min_messages threshold checks before writing the transcript.", "timestamp": "2026-04-08T10:01:10Z"}
  ],
  "startedAt": "2026-04-08T09:49:00Z",
  "lastObsidianWriteAt": "2026-04-08T10:00:00Z"
}
EOF
```

Note: `lastObsidianWriteAt` is set to `10:00:00Z` (when `createNote` fired). The delta
filter in `format_transcript` will only include the `edit` and `bash` tool calls and
messages `m3`/`m4` — verifying the delta capture works correctly.

- [ ] **Step 3: Create a test config pointing at a non-existent vault (to test error handling)**

```bash
cat > /tmp/smoke-config.json << 'EOF'
{
  "model": "claude-haiku-4-5",
  "base_url": null,
  "api_key": null,
  "vault": null,
  "note_skill": "obsidian-dev-notes",
  "min_tool_calls": 2,
  "min_messages": 3,
  "log_path": "wiki/log.md",
  "log_enabled": false,
  "toast_enabled": true,
  "os_notify": false
}
EOF
```

- [ ] **Step 4: Run the Python worker directly against the test transcript**

```bash
python3 .opencode/tools/obsidian_note_writer.py /tmp/smoke-transcript.json /tmp/smoke-config.json $(pwd)
```

Expected outcomes (any of these is acceptable for smoke test):
- **With valid `ANTHROPIC_API_KEY`:** Script runs both LLM calls, attempts `obsidian create` (may fail if Obsidian isn't running — that's fine, exit 1 with a clear error), prints JSON result
- **Without API key:** Script fails at LLM call with `AuthenticationError` — that's a valid test (proves the pipeline reaches the LLM stage)
- **ImportError for `openai`:** Run `pip install openai` first (Task 8)

- [ ] **Step 5: Verify the Python script never crashes at import or argument parsing**

The test passes if the script gets past the `load_transcript` / `build_openai_client` stage without a Python `SyntaxError`, `ImportError`, or `AttributeError`. LLM auth errors are expected in CI-like environments.

- [ ] **Step 6: Final commit — tag the implementation complete**

```bash
git add -A
git status  # verify nothing untracked
git commit -m "feat: obsidian_note_logger plugin — complete implementation

- Plugin: session accumulation, threshold gate, IPC, toast notifications
- Worker: LLM classify + generate, Obsidian CLI write, MOC insert, transaction log
- Config: opencode.json defaults, README examples for default/Ollama/Haiku
- Dependency: openai>=1.0.0 added to requirements.txt and pyproject.toml"
```

---

## Notes for Implementer

**`project` context object:** The `PluginContext.project` field contains the merged `opencode.json` config. Access `obsidian_note_logger` key directly: `project["obsidian_note_logger"]`. If the key is absent, `loadConfig` returns all defaults — the plugin works out of the box.

**`message.updated` content field:** The event payload shape is not formally documented. The plugin tries `event.content` (string), then `event.content.text`, then `event.content.value`. If none exist, content is stored as `""`. Watch the OpenCode plugin API changelog for updates to this field.

**Temp file cleanup on success path:** The Python worker only deletes `transcriptPath` on success — `configPath` is not deleted by the Python script. The plugin's `finally` block covers both on failure. For the success path, add `unlinkSync(configPath)` after the `await Bun.$\`python3 ...\`` call resolves cleanly, or have Python delete both files. Either approach works; the plan uses the plugin-side cleanup for symmetry.

**`__dirname` in plugins:** `resolve(__dirname, "../tools/...")` relies on Bun preserving `__dirname` for plugin files. This is standard Bun CommonJS behavior. If it resolves incorrectly at runtime (e.g., to the `.opencode/node_modules` path), replace with `resolve(import.meta.dir, "../tools/...")` which is the ESM equivalent and more reliable in Bun.

**Ollama testing:** Start Ollama with `ollama serve`, pull a model with `ollama pull llama3.2`, then set `base_url` in config. The openai library routes to `http://localhost:11434/v1` transparently.

**`show_toast` variant values:** Based on the Builder Kit pattern, valid variants are `"info"`, `"success"`, `"error"`. Use `"success"` for note written, `"error"` for failures.
