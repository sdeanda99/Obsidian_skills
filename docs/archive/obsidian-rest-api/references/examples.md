# Practical Examples

Copy-paste-ready examples for common Obsidian REST API operations.

## Table of Contents

- [Reading Notes](#reading-notes)
- [Creating Notes](#creating-notes)
- [Updating Notes](#updating-notes)
- [Deleting Notes](#deleting-notes)
- [Managing Frontmatter](#managing-frontmatter)
- [Working with Headings](#working-with-headings)
- [Working with Blocks](#working-with-blocks)
- [Working with Active Files](#working-with-active-files)
- [Document Maps](#document-maps)
- [Vault Navigation](#vault-navigation)

## Reading Notes

### Read Note as Markdown

**Use case:** Get the raw markdown content of a note.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

**Expected response:**
```markdown
---
title: My Note
tags: [example, test]
---

# My Note

This is the content of my note.
```

### Read Note with Full Metadata

**Use case:** Get note content plus all metadata (frontmatter, tags, file stats).

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.note+json" \
     http://localhost:27123/vault/MyNote.md
```

**Expected response:**
```json
{
  "content": "---\ntitle: My Note\ntags: [example, test]\n---\n\n# My Note\n\nThis is the content of my note.",
  "path": "MyNote.md",
  "frontmatter": {
    "title": "My Note",
    "tags": ["example", "test"]
  },
  "tags": ["example", "test"],
  "stat": {
    "ctime": 1640000000000,
    "mtime": 1640100000000,
    "size": 256
  }
}
```

### Read Note from Subfolder

**Use case:** Access notes in subdirectories.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/Projects/2026/ProjectPlan.md
```

## Creating Notes

### Create Simple Note

**Use case:** Create a new note with basic markdown content.

**Command:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# My New Note

This is a simple note created via API.

## Section 1

Content here." \
     http://localhost:27123/vault/NewNote.md
```

**Result:** Creates `NewNote.md` in vault root.

### Create Note with Frontmatter

**Use case:** Create a note with YAML frontmatter metadata.

**Command:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d $'---
title: Project Planning
tags: [project, planning, 2026]
status: in-progress
priority: high
date: 2026-01-25
---

# Project Planning

## Goals

- Define project scope
- Set milestones
- Assign resources' \
     http://localhost:27123/vault/ProjectPlanning.md
```

**Result:** Creates `ProjectPlanning.md` with frontmatter.

### Create Note in Subfolder

**Use case:** Organize notes in folders (creates folders automatically).

**Command:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# Meeting Notes

Date: 2026-01-25
Attendees: Team

## Discussion Points

- Topic 1
- Topic 2" \
     http://localhost:27123/vault/Meetings/2026/Jan-25-Meeting.md
```

**Result:** Creates `Meetings/2026/` folders if needed, then creates note.

## Updating Notes

### Append Content to End of Note

**Use case:** Add new content to the end of an existing note.

**Command:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "

## Update - $(date +%Y-%m-%d)

New information added via API." \
     http://localhost:27123/vault/MyNote.md
```

**Result:** Appends the content to the end of `MyNote.md`.

### Overwrite Entire Note

**Use case:** Replace all content in a note.

**Command:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# Completely New Content

This replaces everything that was in the note before." \
     http://localhost:27123/vault/MyNote.md
```

**Result:** Completely replaces `MyNote.md` content.

## Deleting Notes

### Delete a Note

**Use case:** Remove a note from the vault.

**Command:**
```bash
curl -X DELETE \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/ObsoleteNote.md
```

**Result:** Deletes `ObsoleteNote.md` (moves to system trash if available).

### Delete Note in Subfolder

**Use case:** Remove a note from a specific folder.

**Command:**
```bash
curl -X DELETE \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/Archive/2025/OldProject.md
```

## Managing Frontmatter

### Replace Frontmatter Field Value

**Use case:** Update an existing frontmatter field.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: status" \
     -H "Content-Type: application/json" \
     -d '"completed"' \
     http://localhost:27123/vault/ProjectPlanning.md
```

**Before:**
```yaml
---
status: in-progress
---
```

**After:**
```yaml
---
status: completed
---
```

### Add New Frontmatter Field

**Use case:** Insert a new field that doesn't exist yet.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: priority" \
     -H "Content-Type: application/json" \
     -d '"high"' \
     http://localhost:27123/vault/ProjectPlanning.md
```

**Result:** Adds `priority: high` to frontmatter.

### Update Frontmatter Array Field

**Use case:** Replace tags or other array fields.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: tags" \
     -H "Content-Type: application/json" \
     -d '["project", "planning", "2026", "important"]' \
     http://localhost:27123/vault/ProjectPlanning.md
```

**Result:** Replaces tags array with new values.

### Append to Frontmatter Array

**Use case:** Add a tag to existing tags without replacing all.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: frontmatter" \
     -H "Target: tags" \
     -H "Content-Type: application/json" \
     -d '"urgent"' \
     http://localhost:27123/vault/ProjectPlanning.md
```

**Before:**
```yaml
tags: [project, planning]
```

**After:**
```yaml
tags: [project, planning, urgent]
```

### Remove Frontmatter Field

**Use case:** Delete a frontmatter field entirely.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: remove" \
     -H "Target-Type: frontmatter" \
     -H "Target: draft" \
     http://localhost:27123/vault/MyNote.md
```

**Result:** Removes `draft` field from frontmatter.

## Working with Headings

### Append Content Under a Heading

**Use case:** Add content to a specific section of a note.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: Meeting Notes" \
     -H "Content-Type: text/markdown" \
     -d "
- Action item: Follow up with client
- Action item: Update documentation" \
     http://localhost:27123/vault/MyNote.md
```

**Before:**
```markdown
## Meeting Notes

- Discussed project timeline
```

**After:**
```markdown
## Meeting Notes

- Discussed project timeline
- Action item: Follow up with client
- Action item: Update documentation
```

### Prepend Content Before Heading Content

**Use case:** Insert content at the beginning of a section.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: prepend" \
     -H "Target-Type: heading" \
     -H "Target: Tasks" \
     -H "Content-Type: text/markdown" \
     -d "
**Priority Tasks:**
" \
     http://localhost:27123/vault/MyNote.md
```

### Replace Content Under Heading

**Use case:** Completely replace a section's content.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: heading" \
     -H "Target: Summary" \
     -H "Content-Type: text/markdown" \
     -d "
Updated summary content with new information." \
     http://localhost:27123/vault/MyNote.md
```

### Target Nested Heading

**Use case:** Update content under a subheading.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: Project Overview::Technical Requirements" \
     -H "Target-Delimiter: ::" \
     -H "Content-Type: text/markdown" \
     -d "
- Additional requirement: API integration" \
     http://localhost:27123/vault/ProjectPlan.md
```

**Note:** Uses `::` to separate parent and child headings.

## Working with Blocks

### Append Content to Block Reference

**Use case:** Add content after a block with a reference ID.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: block" \
     -H "Target: summary-block" \
     -H "Content-Type: text/markdown" \
     -d "

Additional notes related to the summary." \
     http://localhost:27123/vault/MyNote.md
```

**Before:**
```markdown
This is the summary paragraph. ^summary-block
```

**After:**
```markdown
This is the summary paragraph. ^summary-block

Additional notes related to the summary.
```

### Replace Block Content

**Use case:** Update a specific block of content.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: block" \
     -H "Target: stats-block" \
     -H "Content-Type: text/markdown" \
     -d "Updated statistics: 95% completion rate" \
     http://localhost:27123/vault/Report.md
```

### Append Row to Table (via Block Reference)

**Use case:** Add a new row to a table that has a block reference.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: block" \
     -H "Target: data-table" \
     -H "Content-Type: application/json" \
     -d '[["New Item", "100", "Active"]]' \
     http://localhost:27123/vault/DataSheet.md
```

**Before:**
```markdown
| Item | Value | Status |
|------|-------|--------|
| A    | 50    | Done   |
| B    | 75    | Pending|

^data-table
```

**After:**
```markdown
| Item | Value | Status |
|------|-------|--------|
| A    | 50    | Done   |
| B    | 75    | Pending|
| New Item | 100 | Active |

^data-table
```

**Note:** Using `application/json` with array of arrays automatically formats as table rows.

## Working with Active Files

### Read Currently Active File

**Use case:** Get content of the note currently open in Obsidian.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/active/
```

### Append to Active File

**Use case:** Add content to whatever note is currently open.

**Command:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "

---

**Note added:** $(date)

This was appended to the active file." \
     http://localhost:27123/active/
```

### Update Active File Frontmatter

**Use case:** Update metadata of the currently open note.

**Command:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: last-modified" \
     -H "Content-Type: application/json" \
     -d '"2026-01-25"' \
     http://localhost:27123/active/
```

## Document Maps

### Get Document Structure

**Use case:** Discover headings, blocks, and frontmatter fields in a note.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.document-map+json" \
     http://localhost:27123/vault/MyNote.md
```

**Expected response:**
```json
{
  "headings": [
    "# My Note",
    "## Section 1",
    "### Subsection 1.1",
    "## Section 2"
  ],
  "blocks": [
    "^intro-block",
    "^summary-block",
    "^data-table"
  ],
  "frontmatterFields": [
    "title",
    "tags",
    "date",
    "status"
  ]
}
```

**Use case:** Use this to determine valid targets for PATCH operations.

### Analyze Note Before Updating

**Use case:** Check what sections exist before making targeted updates.

**Command:**
```bash
# First, get the document map
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.document-map+json" \
     http://localhost:27123/vault/ProjectPlan.md

# Then use the discovered headings/blocks to target PATCH operations
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: Budget" \
     -d "
- Additional expense: $500" \
     http://localhost:27123/vault/ProjectPlan.md
```

## Vault Navigation

### List Files in Vault Root

**Use case:** Discover what notes exist in the vault.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/
```

**Expected response:**
```json
{
  "files": [
    "MyNote.md",
    "ProjectPlan.md",
    "Meetings/",
    "Archive/"
  ]
}
```

**Note:** Directories end with `/`.

### List Files in Specific Folder

**Use case:** Browse notes in a subfolder.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/Meetings/
```

**Expected response:**
```json
{
  "files": [
    "2026-01-15-Weekly.md",
    "2026-01-22-Weekly.md",
    "2026/"
  ]
}
```

### List Nested Folder Contents

**Use case:** Navigate deep folder structures.

**Command:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/Projects/2026/Q1/
```

## Combined Workflows

### Create Note with Template Structure

**Use case:** Create a new note following a specific template.

**Command:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d $'---
title: Weekly Report
date: 2026-01-25
type: report
status: draft
---

# Weekly Report - Week of 2026-01-25

## Summary

[Summary goes here]

## Accomplishments

- 

## Challenges

- 

## Next Week Goals

- 

## Notes

' \
     http://localhost:27123/vault/Reports/2026-01-25-Weekly.md
```

### Update Multiple Fields in Sequence

**Use case:** Make several updates to different parts of a note.

**Commands:**
```bash
# Update status
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: status" \
     -H "Content-Type: application/json" \
     -d '"in-review"' \
     http://localhost:27123/vault/Report.md

# Add summary
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: Summary" \
     -d "
All goals for this period were met." \
     http://localhost:27123/vault/Report.md

# Append notes
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "

---

_Report finalized on $(date +%Y-%m-%d)_" \
     http://localhost:27123/vault/Report.md
```

### Read, Modify, Update Pattern

**Use case:** Read current content, process it, then update.

**Commands:**
```bash
# 1. Read current content
current_content=$(curl -s -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/Counter.md)

# 2. Process content (example: increment a counter)
# [Your processing logic here]

# 3. Update with new content
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "$updated_content" \
     http://localhost:27123/vault/Counter.md
```

## Error Handling Examples

### Check if Note Exists

**Command:**
```bash
if curl -f -s -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md > /dev/null 2>&1; then
    echo "Note exists"
else
    echo "Note not found (404)"
fi
```

### Handle Missing API Key

**Command:**
```bash
if [ -z "$obsidian_api_keys" ]; then
    echo "Error: obsidian_api_keys not set in environment"
    exit 1
fi

curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

### Verbose Output for Debugging

**Command:**
```bash
curl -v -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

**Shows:**
- Full HTTP request headers
- Full HTTP response headers
- Status codes
- Response body

## Tips & Best Practices

### Environment Variables

Store your API key securely:

```bash
# In your .env file
obsidian_api_keys=your_api_key_here

# Source it before using
source .env

# Or export it
export obsidian_api_keys=your_api_key_here
```

### Escaping Special Characters

For bash/shell scripts with multi-line content:

```bash
# Use $'...' for string with escape sequences
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d $'Line 1\nLine 2\nLine 3' \
     http://localhost:27123/vault/MyNote.md
```

### JSON vs Markdown Content

- Use `Content-Type: text/markdown` for note content
- Use `Content-Type: application/json` for frontmatter updates
- JSON format is smarter about arrays and structured data

### Testing Safely

Test on a copy of your vault or use a test vault:

```bash
# Open Obsidian with a test vault first
# Then run your API commands against it
```
