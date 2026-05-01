---
name: note-attach
description: >
  Attaches orphaned vault notes to their correct project MOC. Use when notes
  exist that were written by the auto-note pipeline without being linked to
  a MOC (e.g. because the project slug was miscased or the MOC wasn't found).
  Triggers: "attach notes", "orphaned notes", "notes not in MOC",
  "fix unlinked notes", "note-attach", "notes missing from MOC",
  "pipeline wrote notes but MOC wasn't updated".
  Reads wiki/log.md audit trail, compares notes against MOC content,
  inserts wikilinks into the correct MOC sections, and back-links the MOC
  in each note's ## Related section.
compatibility: opencode
license: MIT
---

# Note Attach

Guided workflow for attaching orphaned notes to the correct project MOC.
Uses the vault audit log and MOC content comparison to ensure correct
section placement.

---

## Overview

When the auto-note pipeline writes notes but cannot find the project MOC
(due to slug casing mismatch or missing config), the notes are created but
never linked. This skill invokes the `@note-attach` subagent to find those
notes via the audit log and attach them to the correct MOC.

---

## When to Use

- After seeing `MOC warning: MOC not found` entries in `wiki/log.md`
- When a user says "notes aren't in the MOC" or "fix unlinked notes"
- After `init-new-moc` ran but the existing MOC wasn't found by the pipeline
- As a cleanup step after fixing a project slug mismatch

---

## How to Invoke

1. **Identify the project and MOC path:**
   - Ask the user which project's orphans to attach, OR
   - Check `wiki/log.md` for `MOC not found` entries to identify the project
   - Resolve the actual MOC filename: `ls Projects/` in the vault to get
     the exact casing (e.g. `OpenclawSetup-MOC.md`, not `Openclawsetup-MOC.md`)

2. **Invoke the subagent:**
   ```
   @note-attach Please attach all orphaned notes for project slug
   "openclawsetup" to MOC at "Projects/OpenclawSetup-MOC.md" in vault
   "Diddys_Diaries". Use wiki/log.md to identify orphans.
   ```

3. **Review the report** — the agent will list every note attached, every
   note skipped (with reason), and every back-link added.

4. **Run @notedrift after** — once notes are attached, run notedrift to
   enrich cross-links between the newly attached notes.

---

## What NoteAttach Does (and Does NOT Do)

**Does:**
- Reads `wiki/log.md` to find notes flagged with `MOC not found`
- Reads the target MOC to understand existing structure and links
- Reads each orphaned note to determine correct section placement
- Inserts wikilinks into MOC under correct headings (Architecture Decisions /
  Patterns / Learnings) in a single batched write
- Adds `[[MOC-stem]]` to `## Related` in each orphaned note
- Reports exactly what was attached and what was skipped

**Does NOT:**
- Create new notes
- Delete anything
- Rewrite note bodies
- Attach notes that don't belong to the target project

---

## After Attaching

Always run `@notedrift` afterward to enrich cross-links between the
newly-attached notes:

```
@notedrift Please realign the openclawsetup project MOC and enrich
cross-links between notes.
```
