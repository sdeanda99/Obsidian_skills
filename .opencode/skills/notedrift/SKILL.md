---
name: notedrift
description: >
  Use when the user asks to realign notes, fix note drift, update the MOC,
  or sync Obsidian. Triggers: "realign", "notedrift", "update MOC",
  "note drift", "fix my notes", "sync obsidian", "notes are out of date".
  Invokes the @notedrift subagent which reads vault state, identifies gaps
  between the MOC and existing notes, updates MOC links and cross-links
  between related notes, and reports what changed.
compatibility: opencode
license: MIT
---

## Overview

The NoteDrift skill invokes the `@notedrift` subagent to assess and fix
drift between the Obsidian project MOC and the actual notes in
Decisions/, Patterns/, and Learnings/.

## When to Use

- After a heavy dev session where multiple notes were written automatically
- When the user says "my notes are out of date" or "realign obsidian"
- Before a project handoff or review
- As a weekly maintenance step

## How to Invoke

1. Ask the user which project to realign (or use current project from opencode.json vault config)
2. Invoke the subagent:
   ```
   @notedrift Please realign the <project-slug> project MOC and enrich cross-links.
   ```
3. The subagent will report all changes made when finished
4. Relay the summary to the user

## What NoteDrift Does (and Does NOT Do)

**Does:**
- Adds missing wikilinks to the project MOC under correct headings
- Enriches cross-links between related notes (top 5 pairs max)
- Updates the MOC `updated` frontmatter date
- May rewrite the MOC Overview only if clearly factually outdated

**Does NOT:**
- Create new stub notes
- Delete anything
- Rewrite entire note bodies
- Modify notes that don't belong to the target project

## Dry Run

To preview changes without writing: instruct @notedrift to report what it
WOULD change without making edits. Ask it to "assess and report only, do not write."
