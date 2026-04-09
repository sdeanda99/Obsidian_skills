#!/usr/bin/env python3
"""
obsidian_note_writer.py — Worker script for the obsidian_note_logger plugin.

Usage: python3 obsidian_note_writer.py <transcript_json_path> <config_json_path> [worktree]

Reads a SessionData JSON transcript produced by the plugin, runs two LLM calls
(classify then generate), writes a note to Obsidian via CLI, and appends to the
transaction log. Exits 0 on success or skip; exits 1 on unrecoverable failure.
"""

import sys
import json
import os
import subprocess
import datetime
import urllib.request
import urllib.parse
from dataclasses import dataclass
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


def load_transcript(transcript_path: str) -> dict:
    """Load and validate the SessionData JSON from the plugin."""
    with open(transcript_path) as f:
        data = json.load(f)
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
    cutoff = session.get("lastObsidianWriteAt")

    all_tool_calls = session.get("toolCalls", [])
    all_messages = session.get("messages", [])

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
        content = (msg.get("content") or "")[:2000]
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


@dataclass
class ClassifyResult:
    should_capture: bool
    note_type: str
    project: str
    topics: list
    reasoning: str


def classify_and_extract(
    client, model: str, transcript: str, skill_prompt: str
) -> ClassifyResult:
    """
    Gate D: Merged classify + context extract call using json_object structured output.
    Returns ClassifyResult. Falls back to text parsing if provider rejects json_object mode.
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
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

    return ClassifyResult(
        should_capture=bool(data.get("should_capture", False)),
        note_type=data.get("note_type", "decision"),
        project=data.get("project", "unknown"),
        topics=data.get("topics", []),
        reasoning=data.get("reasoning", ""),
    )


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
        return []

    matches = [
        r
        for r in results
        if r.get("path", "").startswith(folder_prefix)
        and r.get("score", 0) >= score_threshold
    ]

    related = []
    for match in matches[:2]:
        path = match["path"]
        code, content, _ = obsidian_run(["read", f"path={path}"], vault=vault)
        if code == 0 and content:
            related.append({"path": path, "content": content})

    return related


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

    Returns dict with keys: action, path, content, existing_path
    Raises ValueError/AssertionError if LLM output is not valid JSON or missing keys.
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

You MUST respond with a JSON object — no markdown fences:
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
                {
                    "role": "user",
                    "content": (
                        f"Project: {classification.project}\n"
                        f"Topics: {', '.join(classification.topics)}\n"
                        f"Classification: {classification.reasoning}\n\n"
                        f"Session transcript:\n\n{transcript}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content)
    except Exception:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Project: {classification.project}\n"
                        f"Topics: {', '.join(classification.topics)}\n"
                        f"Classification: {classification.reasoning}\n\n"
                        f"Session transcript:\n\n{transcript}"
                    ),
                },
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

    assert "action" in data and "path" in data and "content" in data, (
        f"LLM response missing required keys: {list(data.keys())}"
    )
    return data


def write_note(path: str, content: str, vault: str | None) -> tuple[bool, str]:
    """Write a note to Obsidian via CLI. Returns (success, error_message)."""
    code, stdout, stderr = obsidian_run(
        ["create", f"path={path}", f"content={content}", "overwrite=false"],
        vault=vault,
    )
    if code != 0:
        return False, stderr or stdout or "Unknown CLI error"
    return True, ""


def insert_moc_link(
    note_path: str, note_type: str, vault: str | None
) -> tuple[bool, str]:
    """
    Insert a wikilink to the note into the project MOC under the appropriate heading.
    Returns (success, warning_or_error).
    """
    code, content, stderr = obsidian_run(["read", f"path={note_path}"], vault=vault)
    if code != 0:
        return False, f"Could not read newly created note: {stderr}"

    project = None
    for line in content.splitlines():
        if line.startswith("project:"):
            project = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if not project:
        return (
            False,
            "No 'project' field found in note frontmatter — skipping MOC insert",
        )

    moc_path = f"Projects/{project}.md"
    code, moc_content, _ = obsidian_run(["read", f"path={moc_path}"], vault=vault)
    if code != 0:
        return (
            False,
            f"MOC not found at {moc_path} — skipping MOC insert (note was still created)",
        )

    heading_map = {"decision": "## Decisions", "pattern": "## Patterns"}
    heading = heading_map.get(note_type.lower(), "## Notes")

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


def append_log(config: dict, vault: str | None, entry: str) -> None:
    """Append an entry to wiki/log.md in the vault. Silently ignores failures."""
    if not config.get("log_enabled", True):
        return
    log_path = config.get("log_path", "wiki/log.md")
    content = f"\n{entry}\n"
    try:
        obsidian_run(["append", f"path={log_path}", f"content={content}"], vault=vault)
    except Exception:
        pass


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
        pass


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: obsidian_note_writer.py <transcript.json> <config.json> [worktree]",
            file=sys.stderr,
        )
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
        classification = classify_and_extract(
            client, model, transcript_text, skill_prompt
        )
    except Exception as e:
        print(f"LLM classification failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not classification.should_capture:
        append_log(
            config,
            vault,
            (
                f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — Skipped (not a decision/pattern)\n"
                f"- **Session:** {session_id}\n"
                f"- **Reason:** {classification.reasoning}"
            ),
        )
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
            classification.project,
            classification.topics,
            classification.note_type,
            vault,
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
            client, model, transcript_text, skill_prompt, classification, existing_notes
        )
    except (ValueError, AssertionError, Exception) as e:
        print(f"Note generation failed: {e}", file=sys.stderr)
        append_log(
            config,
            vault,
            (
                f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: note generation failed\n"
                f"- **Session:** {session_id}\n"
                f"- **Error:** {e}"
            ),
        )
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

    write_args = [
        "create",
        f"path={write_path}",
        f"content={note_content}",
        overwrite_flag,
    ]
    code, stdout, stderr = obsidian_run(write_args, vault=vault)
    if code != 0:
        err = stderr or stdout or "Unknown CLI error"
        if action == "enrich":
            write_args2 = [
                "create",
                f"path={note_path}",
                f"content={note_content}",
                "overwrite=false",
            ]
            code2, _, _ = obsidian_run(write_args2, vault=vault)
            if code2 == 0:
                action_label = (
                    f"Created (enrich fallback — original write failed: {err})"
                )
                write_path = note_path
            else:
                print(f"Obsidian write failed: {err}", file=sys.stderr)
                append_log(
                    config,
                    vault,
                    (
                        f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: write failed\n"
                        f"- **Session:** {session_id}\n"
                        f"- **Error:** obsidian CLI returned non-zero exit code\n"
                        f"- **Raw:** {err}"
                    ),
                )
                sys.exit(1)
        else:
            print(f"Obsidian write failed: {err}", file=sys.stderr)
            append_log(
                config,
                vault,
                (
                    f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: write failed\n"
                    f"- **Session:** {session_id}\n"
                    f"- **Error:** obsidian CLI returned non-zero exit code\n"
                    f"- **Raw:** {err}"
                ),
            )
            sys.exit(1)

    # --- MOC insert (best-effort) ---
    moc_ok, moc_warn = insert_moc_link(write_path, note_type, vault)
    moc_note = f"\n- **MOC warning:** {moc_warn}" if not moc_ok else ""

    # --- Transaction log ---
    cutoff = session.get("lastObsidianWriteAt")
    delta_window = f"since {cutoff}" if cutoff else "full session"
    tool_count = len(session.get("toolCalls", []))
    msg_count = len(session.get("messages", []))
    base_url = config.get("base_url") or "cloud"
    provider_label = "ollama" if "11434" in base_url else base_url
    append_log(
        config,
        vault,
        (
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
        ),
    )

    # --- OS notification ---
    os_notify(config, "OpenCode → Obsidian", f"Note written: {note_path}")

    # --- Clean up temp files ---
    for tmp in [transcript_path, config_path]:
        try:
            Path(tmp).unlink()
        except Exception:
            pass

    print(json.dumps({"status": "written", "path": note_path}))
    sys.exit(0)
