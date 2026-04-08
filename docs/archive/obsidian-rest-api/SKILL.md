---
name: obsidian-rest-api
description: Interact with Obsidian vault using the Local REST API plugin. Use when you need to create, read, update, delete notes, or manage front-matter metadata and tags. Requires Local REST API plugin with API key authentication. For searching notes, use the omnisearch tool instead.
---

# Obsidian REST API

## Overview

This skill enables AI agents to interact with Obsidian vaults via HTTP requests using the Local REST API plugin. Use this skill for:

- **Creating notes** - Add new notes with optional front-matter metadata
- **Reading notes** - Retrieve note content in markdown or JSON format with metadata
- **Updating notes** - Append content, overwrite notes, or make targeted changes to specific sections
- **Deleting notes** - Remove notes from the vault
- **Managing metadata** - Update front-matter fields and tags
- **Working with active files** - Interact with the currently open note in Obsidian

**Prerequisites:**
- Obsidian installed with Local REST API plugin enabled
- API key configured (stored in `.env` as `obsidian_api_keys`)
- Plugin running on default port (typically `http://localhost:27123`)

**Important:** For searching vault content by keywords or phrases, use the `omnisearch` custom tool instead. This skill focuses on CRUD operations and metadata management, while omnisearch specializes in search functionality.

## Quick Start

### Authentication Setup

The Local REST API uses Bearer token authentication. Your API key should already be configured:

1. **Locate your API key** in Obsidian: Settings → Plugins → Local REST API
2. **Verify it's in `.env`** as `obsidian_api_keys=YOUR_KEY_HERE`
3. **Default base URL** is `http://localhost:27123`

### Test Your Connection

Verify the API is accessible:

```bash
curl http://localhost:27123/
```

Expected response: Basic vault information or API status.

### Your First API Call

Read a note from your vault:

```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

This returns the raw markdown content of `MyNote.md`.

For detailed authentication setup, troubleshooting, and configuration options, see `references/authentication.md`.

## Core Operations

### Read Notes

Retrieve note content in different formats:

**Markdown format** (default):
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/path/to/note.md
```

**JSON format with metadata** (includes front-matter, tags, timestamps):
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.note+json" \
     http://localhost:27123/vault/path/to/note.md
```

The JSON response includes:
- `content` - Full markdown content
- `frontmatter` - Parsed YAML front-matter as object
- `tags` - Array of tags found in the note
- `stat` - File metadata (created time, modified time, size)
- `path` - Full path within vault

Use JSON format when you need to inspect or modify metadata programmatically.

### Create Notes

Create a new note using `PUT`:

**Simple note:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# My New Note\n\nContent here" \
     http://localhost:27123/vault/NewNote.md
```

**Note with front-matter:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d $'---\ntitle: My Note\ntags: [project, important]\nstatus: draft\n---\n\n# Content\n\nNote body here' \
     http://localhost:27123/vault/ProjectNote.md
```

Notes are created at the specified path. Directories are created automatically if needed.

### Update Notes

Three methods for updating existing notes:

**Append content** using `POST`:
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "\n\n## New Section\n\nAdditional content" \
     http://localhost:27123/vault/MyNote.md
```

**Overwrite entire note** using `PUT`:
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "Completely new content" \
     http://localhost:27123/vault/MyNote.md
```

**Targeted updates** using `PATCH` (see Advanced Features section).

### Delete Notes

Remove a note from the vault:

```bash
curl -X DELETE \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

Deletion is permanent. The file moves to system trash if available.

### Manage Metadata

Update front-matter fields without rewriting the entire note using `PATCH`:

**Replace a field value:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: status" \
     -H "Content-Type: application/json" \
     -d '"completed"' \
     http://localhost:27123/vault/MyNote.md
```

**Add a new field:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: insert" \
     -H "Target-Type: frontmatter" \
     -H "Target: priority" \
     -H "Content-Type: application/json" \
     -d '"high"' \
     http://localhost:27123/vault/MyNote.md
```

**Remove a field:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: remove" \
     -H "Target-Type: frontmatter" \
     -H "Target: draft" \
     http://localhost:27123/vault/MyNote.md
```

Tags are managed via front-matter updates or by modifying the `tags` array field.

## Working with Active File

The `/active/` endpoint operates on the currently open note in Obsidian UI:

**Read active file:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/active/
```

**Update active file** (same operations as regular files):
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "\n\nAppended to active file" \
     http://localhost:27123/active/
```

This is useful for interactive workflows where the user has a note open and wants to modify it without specifying the path.

## Advanced Features

### PATCH Operations

`PATCH` requests enable surgical updates to specific parts of notes using three headers:

- **Operation**: `insert`, `append`, `prepend`, `replace`, `remove`
- **Target-Type**: `frontmatter`, `heading`, `block`, `tag`
- **Target**: Specific identifier (field name, heading text, block ID)

**Append content under a heading:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: ## Meeting Notes" \
     -H "Content-Type: text/markdown" \
     -d "\n- Action item added via API" \
     http://localhost:27123/vault/MyNote.md
```

**Replace content of a block:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: block" \
     -H "Target: ^block-id" \
     -d "New block content" \
     http://localhost:27123/vault/MyNote.md
```

### Document Maps

Retrieve structured metadata about a note's contents:

```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.document-map+json" \
     http://localhost:27123/vault/MyNote.md
```

Returns:
- **headings** - Array of all headings with positions
- **blocks** - Array of block IDs and their locations
- **frontmatterFields** - List of front-matter field names
- **tags** - All tags in the document

Use document maps to discover what can be targeted by PATCH operations or to analyze note structure.

### Content Type Negotiation

The API supports multiple response formats via `Accept` headers:

- `text/markdown` - Raw markdown (default)
- `application/vnd.olrapi.note+json` - Content + metadata
- `application/vnd.olrapi.document-map+json` - Structural information

Choose the format based on your needs:
- Use markdown for simple content retrieval
- Use note+json when working with metadata
- Use document-map+json for structure analysis

## Reference Documentation

This skill includes detailed reference documentation for comprehensive usage:

### references/authentication.md
Complete authentication setup guide including:
- Plugin installation steps
- API key location and configuration
- Environment variable setup
- Base URL configuration
- Connection verification
- Troubleshooting common issues

### references/api_endpoints.md
Comprehensive endpoint reference with:
- All available endpoints and HTTP methods
- Required and optional headers
- Request/response formats
- Parameters and their usage
- Minimal examples for each endpoint

### references/examples.md
Practical, copy-paste-ready examples covering:
- Reading notes in different formats
- Creating notes with and without front-matter
- All update methods (append, overwrite, targeted)
- Metadata management workflows
- Working with active files
- Document map usage
- Common error scenarios

### references/mcp_research.md
Research documentation on the MCP server implementation including endpoint mapping and integration patterns. Useful for understanding the relationship between direct REST API usage and MCP server abstractions.

## Best Practices

### When to Use Each Method

- **GET** - Read note content or metadata
- **PUT** - Create new notes or completely replace existing ones
- **POST** - Append content to end of note
- **PATCH** - Make targeted changes (preferred for partial updates)
- **DELETE** - Remove notes

### Path Handling

- Paths are relative to vault root
- Use forward slashes: `folder/subfolder/note.md`
- File extension `.md` is required
- Directories are created automatically when needed

### Error Handling

Common HTTP status codes:
- `200` - Success
- `404` - Note not found
- `401` - Authentication failed (check API key)
- `400` - Bad request (check headers and body format)

### Performance Tips

- Use JSON format when reading multiple pieces of metadata
- Use PATCH for small updates instead of PUT (preserves unchanged content)
- Batch related operations when possible
- Use document maps to discover structure before making changes

## Integration with Other Tools

### Search Operations

**Do not use this skill for searching notes.** Instead, use the `omnisearch` custom tool:

```javascript
// Use omnisearch for search queries
const results = await omnisearch.search("keyword");
```

The omnisearch tool provides:
- Full-text search across vault
- Fuzzy matching
- Search result excerpts with context
- Better performance for search operations

### Workflow Pattern

Typical workflow combining both tools:

1. **Search** for notes using `omnisearch`
2. **Read** specific notes using this skill's GET operations
3. **Update** notes using this skill's PATCH/POST/PUT operations
4. **Create** related notes using this skill's PUT operations

This separation ensures each tool is used for its optimal purpose.
