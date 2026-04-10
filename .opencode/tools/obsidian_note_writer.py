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
import time
import urllib.request
import urllib.parse
import socket as _socket
from dataclasses import dataclass
from pathlib import Path
from openai import BadRequestError


def encode_content(s: str) -> str:
    """Encode newlines and tabs for Obsidian CLI content= arguments."""
    return s.replace("\n", "\\n").replace("\t", "\\t")


class ObsidianClient:
    """
    Three-layer Obsidian write client.
    Tries: (1) IPC socket, (2) Local REST API, (3) direct filesystem.
    All public methods return (success: bool, output: str, error: str).
    """

    def __init__(self, vault_name: str | None, config: dict):
        self.vault_name = vault_name
        self.config = config
        self._sock_path = self._find_sock_path()
        obsidian_cfg = self._read_obsidian_config()
        self._vault_path = self._find_vault_path(vault_name, obsidian_cfg)
        self._rest_key, self._rest_port = self._find_rest_config(
            vault_name, obsidian_cfg
        )

    # ── Backend detection ──────────────────────────────────────────────────

    @staticmethod
    def _read_obsidian_config() -> dict:
        """Read ~/.config/obsidian/obsidian.json. Returns empty dict on any error."""
        try:
            config_path = Path.home() / ".config" / "obsidian" / "obsidian.json"
            return json.loads(config_path.read_text())
        except Exception:
            return {}

    @staticmethod
    def _find_sock_path() -> str | None:
        """Return IPC socket path for current user, or None if not found."""
        xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        candidate = os.path.join(xdg, ".obsidian-cli.sock")
        if os.path.exists(candidate):
            return candidate
        home_candidate = os.path.join(os.path.expanduser("~"), ".obsidian-cli.sock")
        if os.path.exists(home_candidate):
            return home_candidate
        return None

    @staticmethod
    def _find_vault_path(vault_name: str | None, obsidian_config: dict) -> Path | None:
        """
        Resolve vault filesystem path from the pre-loaded obsidian config.
        Matches by vault name (directory name). Returns None if not found.
        """
        try:
            for vault in obsidian_config.get("vaults", {}).values():
                p = Path(vault["path"])
                if vault_name is None or p.name == vault_name:
                    return p
        except Exception:
            pass
        return None

    @staticmethod
    def _find_rest_config(
        vault_name: str | None, obsidian_config: dict
    ) -> tuple[str | None, int]:
        """
        Auto-detect Local REST API key and port from vault plugin data.json.
        Returns (api_key, port). Falls back to (None, 27123).
        """
        DEFAULT_PORT = 27123
        try:
            for vault in obsidian_config.get("vaults", {}).values():
                p = Path(vault["path"])
                if vault_name is None or p.name == vault_name:
                    plugin_data = (
                        p
                        / ".obsidian"
                        / "plugins"
                        / "obsidian-local-rest-api"
                        / "data.json"
                    )
                    if plugin_data.exists():
                        pdata = json.loads(plugin_data.read_text())
                        key = pdata.get("apiKey")
                        port = pdata.get("insecurePort", DEFAULT_PORT)
                        return key, port
        except Exception:
            pass
        return None, DEFAULT_PORT

    # ── IPC layer ──────────────────────────────────────────────────────────

    def _ipc(self, args: list[str]) -> tuple[bool, str, str]:
        """
        Send a command via Obsidian IPC socket.
        Protocol: JSON {"argv": [...], "tty": false, "cwd": "/tmp"} + "\\ndTmIPC\\n"
        vault prefix prepended automatically if vault_name is set.
        Returns (success, stdout, stderr).
        """
        if not self._sock_path:
            return False, "", "IPC socket not found"
        argv = []
        if self.vault_name:
            argv.append(f"vault={self.vault_name}")
        argv.extend(args)
        payload = json.dumps({"argv": argv, "tty": False, "cwd": "/tmp"}) + "\ndTmIPC\n"
        sock = None
        try:
            sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(self._sock_path)
            sock.send(payload.encode())
            time.sleep(0.5)
            chunks = []
            while True:
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                except _socket.timeout:
                    break
            output = b"".join(chunks).decode(errors="replace").strip()
            # IPC errors come back as text starting with "Error:" or similar
            if output.lower().startswith("error"):
                return False, "", output
            return True, output, ""
        except Exception as e:
            return False, "", str(e)
        finally:
            if sock:
                sock.close()

    # ── REST API layer ─────────────────────────────────────────────────────

    def _rest_read(self, path: str) -> tuple[bool, str, str]:
        if not self._rest_key:
            return False, "", "REST API key not available"
        url = f"http://localhost:{self._rest_port}/vault/{urllib.parse.quote(path)}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self._rest_key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return True, r.read().decode(), ""
        except Exception as e:
            return False, "", str(e)

    def _rest_put(self, path: str, content: str) -> tuple[bool, str, str]:
        if not self._rest_key:
            return False, "", "REST API key not available"
        url = f"http://localhost:{self._rest_port}/vault/{urllib.parse.quote(path)}"
        data = content.encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {self._rest_key}",
                "Content-Type": "text/markdown",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return True, str(r.status), ""
        except Exception as e:
            return False, "", str(e)

    def _rest_append(self, path: str, content: str) -> tuple[bool, str, str]:
        if not self._rest_key:
            return False, "", "REST API key not available"
        # POST /vault/{path}/ appends to end of file
        url = f"http://localhost:{self._rest_port}/vault/{urllib.parse.quote(path)}/"
        data = content.encode()
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._rest_key}",
                "Content-Type": "text/markdown",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return True, str(r.status), ""
        except Exception as e:
            return False, "", str(e)

    # ── Filesystem layer ───────────────────────────────────────────────────

    def _fs_read(self, path: str) -> tuple[bool, str, str]:
        if not self._vault_path:
            return False, "", "vault path unknown"
        try:
            return True, (self._vault_path / path).read_text(), ""
        except Exception as e:
            return False, "", str(e)

    def _fs_write(
        self, path: str, content: str, overwrite: bool
    ) -> tuple[bool, str, str]:
        if not self._vault_path:
            return False, "", "vault path unknown"
        try:
            full = self._vault_path / path
            if full.exists() and not overwrite:
                return False, "", f"File exists and overwrite=False: {path}"
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)
            return True, f"Written: {path}", ""
        except Exception as e:
            return False, "", str(e)

    def _fs_append(self, path: str, content: str) -> tuple[bool, str, str]:
        if not self._vault_path:
            return False, "", "vault path unknown"
        try:
            full = self._vault_path / path
            full.parent.mkdir(parents=True, exist_ok=True)
            with open(full, "a") as f:
                f.write(content)
            return True, f"Appended: {path}", ""
        except Exception as e:
            return False, "", str(e)

    # ── Public API (three-layer with fallback) ─────────────────────────────

    def read(self, path: str) -> tuple[bool, str, str]:
        """Read a note. Tries IPC → REST → filesystem."""
        errors = []
        ok, out, err = self._ipc(["read", f"path={path}"])
        if err:
            errors.append(f"IPC: {err}")
        # Fall through if output is empty — an empty IPC response may mean the file
        # wasn't found or the command silently failed; try next backend.
        if ok and out:
            return True, out, ""
        if self._rest_key:
            ok, out, err2 = self._rest_read(path)
            if ok:
                return True, out, ""
            if err2:
                errors.append(f"REST: {err2}")
        ok, out, err3 = self._fs_read(path)
        if ok:
            return True, out, ""
        if err3:
            errors.append(f"FS: {err3}")
        return False, "", "; ".join(errors) if errors else "all backends failed"

    def create(
        self, path: str, content: str, overwrite: bool = False
    ) -> tuple[bool, str, str]:
        """Create or overwrite a note. Tries IPC → REST (if overwrite=True) → filesystem."""
        errors = []
        ipc_args = ["create", f"path={path}", f"content={encode_content(content)}"]
        if overwrite:
            ipc_args.append("overwrite")
        ok, out, err = self._ipc(ipc_args)
        if err:
            errors.append(f"IPC: {err}")
        if ok:
            return True, out, ""
        # REST PUT always overwrites — only use it when overwrite is explicitly True
        if self._rest_key and overwrite:
            ok, out, err2 = self._rest_put(path, content)
            if ok:
                return True, out, ""
            if err2:
                errors.append(f"REST: {err2}")
        ok, out, err3 = self._fs_write(path, content, overwrite)
        if ok:
            return True, out, ""
        if err3:
            errors.append(f"FS: {err3}")
        return False, "", "; ".join(errors) if errors else "all backends failed"

    def append(self, path: str, content: str) -> tuple[bool, str, str]:
        """Append content to a note. Tries IPC → REST → filesystem."""
        errors = []
        ok, out, err = self._ipc(
            ["append", f"path={path}", f"content={encode_content(content)}"]
        )
        if err:
            errors.append(f"IPC: {err}")
        if ok:
            return True, out, ""
        if self._rest_key:
            ok, out, err2 = self._rest_append(path, content)
            if ok:
                return True, out, ""
            if err2:
                errors.append(f"REST: {err2}")
        ok, out, err3 = self._fs_append(path, content)
        if ok:
            return True, out, ""
        if err3:
            errors.append(f"FS: {err3}")
        return False, "", "; ".join(errors) if errors else "all backends failed"


def load_config(config_path: str) -> dict:
    """Load plugin config from the JSON file written by the plugin."""
    with open(config_path) as f:
        return json.load(f)


def resolve_api_key_and_base_url(config: dict) -> tuple[str, str]:
    """
    Resolve API key and base_url together from config → env vars → auth.json.

    Priority:
    1. Explicit config values (model, base_url, api_key)
    2. Env vars (ANTHROPIC_API_KEY → Anthropic endpoint, OPENAI_API_KEY → no base_url)
    3. OpenCode auth.json — prefers openrouter over anthropic because:
       - Anthropic's sk-ant- keys are NOT accepted by their OpenAI-compat endpoint
       - OpenRouter accepts its own keys and proxies to Anthropic correctly
    4. Ollama fallback if base_url contains localhost:11434

    Returns (api_key, base_url).
    """
    explicit_base = config.get("base_url") or ""
    explicit_key = config.get("api_key") or ""

    if explicit_key:
        return explicit_key, explicit_base

    if "localhost:11434" in explicit_base:
        return "ollama", explicit_base

    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ[
            "ANTHROPIC_API_KEY"
        ], explicit_base or "https://api.anthropic.com/v1/"
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"], explicit_base

    # Read from OpenCode auth.json — prefer openrouter (works with OpenAI compat layer)
    # over anthropic (sk-ant- keys are rejected by api.anthropic.com/v1/)
    try:
        auth_path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        auth = json.loads(auth_path.read_text())
        for provider in ("openrouter", "anthropic"):
            if provider in auth and auth[provider].get("key"):
                key = auth[provider]["key"]
                if provider == "openrouter":
                    return key, "https://openrouter.ai/api/v1/"
                else:
                    return key, "https://api.anthropic.com/v1/"
        # First available key of any provider
        for provider_data in auth.values():
            if isinstance(provider_data, dict) and provider_data.get("key"):
                return provider_data["key"], explicit_base
    except Exception:
        pass

    return "", explicit_base


def resolve_model(config: dict, base_url: str) -> str:
    """
    Resolve model name from config → env → fallback.
    Adjusts default model name based on provider (OpenRouter uses namespaced models).
    """
    if config.get("model"):
        return config["model"]
    if os.environ.get("OPENCODE_MODEL"):
        return os.environ["OPENCODE_MODEL"]
    if os.environ.get("ANTHROPIC_DEFAULT_MODEL"):
        return os.environ["ANTHROPIC_DEFAULT_MODEL"]
    # OpenRouter requires provider-namespaced model names
    if "openrouter" in base_url:
        return "anthropic/claude-haiku-4-5"
    return "claude-haiku-4-5"


def build_openai_client(config: dict):
    """Build an openai.OpenAI client from config."""
    from openai import OpenAI

    api_key, base_url = resolve_api_key_and_base_url(config)

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def load_transcript(transcript_path: str) -> dict:
    """Load and validate the SessionData JSON from the plugin."""
    with open(transcript_path) as f:
        data = json.load(f)
    for field in ("sessionID", "toolCalls", "messages"):
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
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
        raw = raw.rsplit("```", 1)[0]
    data = json.loads(raw.strip())

    return ClassifyResult(
        should_capture=bool(data.get("should_capture", False)),
        note_type=data.get("note_type", "decision"),
        project=data.get("project", "unknown"),
        topics=data.get("topics", []),
        reasoning=data.get("reasoning", ""),
    )


def search_related_notes(
    project: str,
    topics: list,
    note_type: str,
    client: ObsidianClient,
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
        ok, content, _ = client.read(path)
        if ok and content:
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

    Uses a delimiter-based output format to avoid JSON escaping issues with
    multiline Markdown content. The LLM outputs metadata as JSON, then the full
    note content as plain text after a "---NOTE---" separator.
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

You MUST respond in exactly this format — two sections separated by the delimiter:

SECTION 1: A JSON object on its own lines (no markdown fences):
{{
  "action": "create",
  "path": "Decisions/YYYY-MM-DD-short-slug.md",
  "existing_path": null
}}

SECTION 2: The literal string ---NOTE--- on its own line, followed by the complete note content.

Example response:
{{"action": "create", "path": "Decisions/{today}-example.md", "existing_path": null}}
---NOTE---
---
type: {classification.note_type}
project: {classification.project}
...
---

## Context
...

Rules:
- action "enrich": set existing_path to the path being updated, path = existing_path
- action "create": set existing_path to null
- path must start with Decisions/ or Patterns/ matching the note type
- path filename (for create): YYYY-MM-DD-kebab-case-slug.md (today is {today})
- The note content after ---NOTE--- is the COMPLETE note (not a diff — full replacement)
- frontmatter fields: type, project, status (decisions only), tags, created, updated
- created and updated should be {today}
- Use the schema from the skill instructions above for section headings
- Be specific — extract actual content from the transcript, not generic summaries
{existing_block}
"""
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

    # Parse delimiter-based format: JSON metadata + ---NOTE--- + note content
    DELIMITER = "---NOTE---"
    if DELIMITER in raw:
        meta_part, note_content = raw.split(DELIMITER, 1)
        note_content = note_content.strip()
        # Strip markdown fences from meta part if present
        meta_part = meta_part.strip()
        if meta_part.startswith("```"):
            meta_part = meta_part.split("```")[1]
            if meta_part.startswith("json"):
                meta_part = meta_part[4:]
        data = json.loads(meta_part.strip())
        data["content"] = note_content
    else:
        # Fallback: try to parse the whole thing as JSON (legacy path)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw.strip())

    assert "action" in data and "path" in data and "content" in data, (
        f"LLM response missing required keys: {list(data.keys())}"
    )
    return data


def insert_moc_link(
    note_path: str, note_type: str, client: ObsidianClient
) -> tuple[bool, str]:
    """
    Insert a wikilink to the note into the project MOC under the appropriate heading.
    Returns (success, warning_or_error).
    """
    ok, content, err = client.read(note_path)
    if not ok:
        return False, f"Could not read newly created note: {err}"

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
    ok, moc_content, _ = client.read(moc_path)
    if not ok:
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
    ok, _, err = client.create(moc_path, new_content, overwrite=True)
    if not ok:
        return False, f"Failed to update MOC: {err}"
    return True, ""


def append_log(config: dict, client: ObsidianClient, entry: str) -> None:
    """Append an entry to wiki/log.md in the vault. Silently ignores failures."""
    if not config.get("log_enabled", True):
        return
    log_path = config.get("log_path", "wiki/log.md")
    content = f"\n{entry}\n"
    try:
        client.append(log_path, content)
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
            safe_msg = message.replace('"', '\\"')
            safe_title = title.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
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
    obsidian = ObsidianClient(vault, config)
    worktree = sys.argv[3] if len(sys.argv) > 3 else os.getcwd()
    skill_prompt = load_skill_prompt(config, worktree)
    transcript_text = format_transcript(session)
    session_id = session["sessionID"]

    try:
        client = build_openai_client(config)
        _, resolved_base_url = resolve_api_key_and_base_url(config)
        model = resolve_model(config, resolved_base_url)
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
            obsidian,
            (
                f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — Skipped (not a decision/pattern)\n"
                f"- **Session:** {session_id}\n"
                f"- **Reason:** {classification.reasoning}"
            ),
        )
        print(json.dumps({"status": "skipped", "reason": classification.reasoning}))
        for tmp in [transcript_path, config_path]:
            try:
                Path(tmp).unlink()
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
            obsidian,
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
    except Exception as e:
        print(f"Note generation failed: {e}", file=sys.stderr)
        append_log(
            config,
            obsidian,
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
        write_path = existing_path
        action_label = f"Enriched {existing_path}"
    else:
        write_path = note_path
        action_label = "Created"

    write_failed = False
    err = ""
    ok, _, err = obsidian.create(
        write_path, note_content, overwrite=(action == "enrich")
    )
    if not ok:
        if action == "enrich":
            ok2, _, _ = obsidian.create(note_path, note_content, overwrite=False)
            if ok2:
                action_label = (
                    f"Created (enrich fallback — original write failed: {err})"
                )
                write_path = note_path
            else:
                write_failed = True
        else:
            write_failed = True

    if write_failed:
        print(f"Obsidian write failed: {err}", file=sys.stderr)
        append_log(
            config,
            obsidian,
            (
                f"## {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} — ERROR: write failed\n"
                f"- **Session:** {session_id}\n"
                f"- **Error:** obsidian write returned failure\n"
                f"- **Raw:** {err}"
            ),
        )
        sys.exit(1)

    # --- MOC insert (best-effort) ---
    moc_ok, moc_warn = insert_moc_link(write_path, note_type, obsidian)
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
        obsidian,
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
    os_notify(config, "OpenCode → Obsidian", f"Note written: {write_path}")

    # --- Clean up temp files ---
    for tmp in [transcript_path, config_path]:
        try:
            Path(tmp).unlink()
        except Exception:
            pass

    print(json.dumps({"status": "written", "path": note_path}))
    sys.exit(0)
