# Multi-Note Sessions, Reasoning Chain Extraction, Ollama & NoteDrift Agent — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the single-note-per-session pipeline into a multi-note system that extracts deep reasoning chains from session transcripts, runs two separate LLM classification paths (full-log for decisions/patterns, sub-arcs for problem-solutions), injects git commit references, wires Ollama as explicit config, bumps note generation to 3000 tokens, and adds a NoteDrift OpenCode subagent for on-demand MOC realignment and cross-link enrichment.

**Architecture:**
- **Path A** — full session log → `classify_decisions_patterns()` → list of decision/pattern/learning notes (no cap on count)
- **Path B** — per-arc error→fix sequences → `classify_arc()` → list of problem-solution notes  
- Both paths feed `generate_note()` independently; main loop writes N+M notes per session idle
- **NoteDrift** — OpenCode subagent (`.opencode/agents/notedrift.md`) invoked via `@notedrift`; uses native obsidian tools to assess drift, update MOC, enrich cross-links

**Tech Stack:** Python 3.11+, `openai` SDK (OpenAI-compat), TypeScript/Bun, OpenCode plugin API, Ollama v0.18 `/v1` compat, git CLI

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.opencode/tools/obsidian_note_writer.py` | **Modify** | Add `ReasoningArc`, `extract_reasoning_chains()`, `format_arc()`, `classify_decisions_patterns()` (Path A), `classify_arc()` (Path B), `classify_multi()` coordinator, `get_session_commits()`, update `generate_note()` max_tokens→3000, rewrite main loop |
| `.opencode/plugins/obsidian_note_logger.ts` | **Modify** | Update stdout parsing for `paths[]` array, update toast message |
| `opencode.json` | **Modify** | Add `ollama_model` config field |
| `.opencode/agents/notedrift.md` | **Create** | NoteDrift subagent — mode, tools, permissions, system prompt |
| `.opencode/skills/notedrift/SKILL.md` | **Create** | Teaches primary agent when and how to invoke `@notedrift` |

---

## Task 1: ReasoningArc dataclass + extract_reasoning_chains() + format_arc()

**File:** `.opencode/tools/obsidian_note_writer.py`

Add after the ClassifyResult dataclass (currently around line 502).

- [ ] Add ERROR_SIGNALS and RESOLUTION_SIGNALS sets + helper functions _is_error() / _is_resolution()
- [ ] Add ReasoningArc dataclass with fields: problem_signal, pre_reasoning, tool_sequence, resolution, post_reasoning, start_ts, end_ts
- [ ] Add extract_reasoning_chains(session) -> list[ReasoningArc]:
  - Build merged timeline of messages + tool calls sorted by timestamp
  - Scan for tool calls where output matches ERROR_SIGNALS
  - For each: capture 5 events back (assistant messages = pre_reasoning, DEEP — no truncation)
  - Capture 10 events forward until RESOLUTION_SIGNAL (post_reasoning + tool_sequence)
  - NO "general arc" — full-log classification (Path A) covers non-error content
- [ ] Add format_arc(arc) -> str — renders arc as LLM-readable reasoning chain
- [ ] Syntax check: `python3 -c "import ast; ast.parse(open('.opencode/tools/obsidian_note_writer.py').read()); print('OK')"`
- [ ] Commit: `feat: ReasoningArc extraction — error→fix arcs from session timeline (deep capture)`

---

## Task 2: Path A — classify_decisions_patterns() — full log → list

**File:** `.opencode/tools/obsidian_note_writer.py`

Replaces classify_and_extract(). Operates on FULL session transcript. Returns list[ClassifyResult] — one per distinct decision/pattern/learning. No cap.

- [ ] Add classify_decisions_patterns(client, model, transcript, skill_prompt) -> list[ClassifyResult]
  - System prompt: identify ALL distinct decisions, patterns, learnings in the transcript
  - Returns JSON: {"items": [{note_type, project, topics, reasoning, patterns_observed}, ...]}
  - DO NOT include problem-solution — that is Path B
  - max_tokens=1500, temperature=0
  - Parse items array → list of ClassifyResult with _arc=None
- [ ] Syntax check
- [ ] Commit: `feat: classify_decisions_patterns — Path A, full log → list of decisions/patterns/learnings`

---

## Task 3: Path B — classify_arc() — single arc → problem-solution

**File:** `.opencode/tools/obsidian_note_writer.py`

Operates on a single formatted ReasoningArc. Returns ClassifyResult(note_type="problem-solution") or None.

- [ ] Add classify_arc(client, model, arc_text, skill_prompt) -> ClassifyResult | None
  - System prompt: assess if this error+fix arc is specific enough to save a future developer time
  - Returns JSON: {should_capture, project, topics, reasoning, problems[], solutions[]}
  - note_type always "problem-solution"
  - max_tokens=600, temperature=0
  - Returns None if should_capture=false
- [ ] Syntax check
- [ ] Commit: `feat: classify_arc — Path B, single reasoning arc → problem-solution classification`

---

## Task 4: classify_multi() coordinator

**File:** `.opencode/tools/obsidian_note_writer.py`

- [ ] Add _arc=None field to ClassifyResult dataclass (optional, carries ReasoningArc for Path B items)
- [ ] Add classify_multi(client, model, session, arcs, skill_prompt, transcript) -> list[ClassifyResult]
  - Run Path A (classify_decisions_patterns) — one LLM call over full transcript
  - Run Path B (classify_arc) — one LLM call per arc
  - Attach arc to result._arc for Path B items
  - Both paths combined — no dedup needed (different note types by design)
  - Log counts to stderr for debugging
- [ ] Syntax check
- [ ] Commit: `feat: classify_multi — coordinates Path A (full log) + Path B (arcs) classification`

---

## Task 5: Git commit refs + generate_note() max_tokens → 3000

**File:** `.opencode/tools/obsidian_note_writer.py`

- [ ] Add get_session_commits(worktree, session) -> list[dict]
  - Run: `git log --format=%H|%s|%ai --after=<session.startedAt> HEAD`
  - Returns list of {hash (8 chars), subject, date} — empty list on any error
- [ ] Add commits: list param to generate_note()
  - Build commits_block: list of "`hash` subject (date)" lines
  - Inject into system prompt with instruction to reference relevant commits inline as `hash`
- [ ] Change generate_note() content param: rename transcript → content
  - Path A items pass full transcript, Path B items pass format_arc(result._arc)
- [ ] Bump max_tokens 2000 → 3000 in generate_note()
- [ ] Syntax check
- [ ] Commit: `feat: git commit refs in notes + generate_note max_tokens 2000→3000`

---

## Task 6: Rewrite __main__ — multi-note loop

**File:** `.opencode/tools/obsidian_note_writer.py`

Replace single-note Gate D + generate + write block with multi-note loop.

- [ ] Call extract_reasoning_chains(session) → arcs
- [ ] Call classify_multi(client, model, session, arcs, skill_prompt, transcript_text) → all_classifications
- [ ] If empty: log "Skipped — no capturable items", exit 0
- [ ] Call get_session_commits(worktree, session) → commits
- [ ] Loop over all_classifications:
  - content_for_generate = format_arc(c._arc) if c._arc else transcript_text
  - search_related_notes() per item
  - generate_note(client, model, content_for_generate, ..., commits)
  - write note + insert_moc_link + append_log (existing logic, now in loop)
  - continue on per-item errors (don't abort entire session)
  - collect written_paths
- [ ] Final print: {"status": "written"|"skipped", "paths": [...]}
- [ ] Syntax check
- [ ] Smoke test: `python3 -c "exec(open('.opencode/tools/obsidian_note_writer.py').read().split('if __name__')[0]); print('Import OK')"`
- [ ] Commit: `feat: multi-note main loop — N notes per session idle via Path A + Path B`

---

## Task 7: Ollama explicit config wiring

**Files:** `.opencode/tools/obsidian_note_writer.py`, `opencode.json`

- [ ] Update resolve_model(): if "11434" in base_url → return config.get("ollama_model") or "qwen2:7b"
- [ ] Update resolve_api_key_and_base_url(): when base_url has 11434 and no explicit key → return ("ollama", base_url)
- [ ] Add ollama_model: null to opencode.json plugin config
- [ ] Syntax check
- [ ] Commit: `feat: explicit Ollama config — ollama_model field, auto-key for local endpoint`

---

## Task 8: Update TypeScript plugin for paths[] array

**File:** `.opencode/plugins/obsidian_note_logger.ts`
**REQUIRES SERVER RESTART**

- [ ] Update stdout parsing in handleSessionIdle:
  - const paths = parsed.paths ?? (parsed.path ? [parsed.path] : [])
  - label = paths.length === 1 ? "Note written: X" : "N notes written to Obsidian"
  - Backward compat: parsed.path fallback handles old single-note format
- [ ] Commit + push
- [ ] Restart server, verify plugin loaded in log

---

## Task 9: NoteDrift subagent — .opencode/agents/notedrift.md

**REQUIRES SERVER RESTART (can batch with Task 8)**

- [ ] Create .opencode/agents/notedrift.md with:
  - mode: subagent, model: anthropic/claude-haiku-4-5, temperature: 0.2, maxSteps: 30
  - tools: bash=false, write=false, edit=false
  - permission: task.*=deny (no sub-subagents)
  - System prompt covering: assess drift → update MOC → enrich cross-links (top 5 pairs) → report
  - Constraints: no new notes, no deletes, no full rewrites, MOC overview rewrite only if clearly outdated
- [ ] Commit + push (batch with Task 8 restart if possible)

---

## Task 10: NoteDrift skill — .opencode/skills/notedrift/SKILL.md

No restart required.

- [ ] Create .opencode/skills/notedrift/SKILL.md with:
  - Triggers: "realign", "notedrift", "update MOC", "note drift", "fix my notes", "sync obsidian"
  - How to invoke: @notedrift with project slug
  - What it does vs. does NOT do
  - Dry run option: instruct @notedrift to report without writing
- [ ] Commit + push

---

## Execution Order

Tasks 1-7: Python only — no restart needed, run sequentially
Task 8+9: Batch together — one restart handles both plugin + agent
Task 10: No restart, can run before or after restart

---

## Success Criteria

- [ ] Session idle produces multiple notes when multiple distinct items exist in the session
- [ ] Problem-solution notes contain the reasoning chain extracted from the error→fix arc
- [ ] Decision/pattern/learning notes are derived from the full session log (not truncated arcs)
- [ ] Generated notes reference git commits from the session timespan (backtick hash inline)
- [ ] wiki/log.md shows multiple entries per session idle with correct note types
- [ ] MOC receives all generated wikilinks under correct headings
- [ ] @notedrift successfully realigns MOC and reports exactly what changed
- [ ] Ollama path works when base_url and ollama_model are set in opencode.json
