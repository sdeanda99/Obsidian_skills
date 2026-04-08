# MCP Server Endpoint Mapping

**Note:** This document describes the MCP (Model Context Protocol) server implementation for Obsidian. For direct REST API usage (which this skill provides), see `api_endpoints.md` and `examples.md` instead. This file is included for reference to understand the relationship between MCP server abstractions and the underlying REST API.

## Search Operations

**Important:** For searching your Obsidian vault, use the `omnisearch` custom tool instead of the REST API search endpoints. The omnisearch tool provides superior search functionality optimized for vault queries.

---

## 1. Repository Overview  

| Path | Purpose |
|------|---------|
| obsidian/ | Root of the MCP server integration with Obsidian. Contains configuration files, example scripts, and a README.md that describes how the server talks to Obsidian via its Local REST API. |
| templates/ | Sample template notes that illustrate how front‑matter metadata is structured for various operations (e.g., tags, timestamps). Useful when you need concrete examples of the JSON/YAML payloads expected by the endpoints. |
| src/ | JavaScript/TypeScript source code of the MCP server. Each tool is implemented as a separate module that internally calls the REST API. |
| test/ | Unit‑ and integration‑tests for each endpoint, giving you ready‑made curl examples and sample responses to validate your own calls. |

---

## 2. Tools → REST Endpoint Mapping  

| MCP Tool (as defined in the server) | Primary / Base REST Endpoint(s) (via Local REST API) | HTTP Method(s) | Key Path/Query Parameters | What It Does |
|-------------------------------------|-------------------------------------------------------|----------------|---------------------------|--------------|
| obsidian_read_note | /vault/{vaultId}/files/{filePath} | GET | - plaintext=true (optional, returns raw markdown) <br> - includeStat=true (optional, adds creation/modified timestamps) | Retrieves the full content of a note and its metadata. If plaintext=false, the response is JSON with fields: content, path, ctime, mtime. |
| obsidian_update_note | /vault/{vaultId}/files/{targetFilePath} | POST (or PUT when using full overwrite) | - `mode={append|prepend|overwrite} <br> - content=<new content> <br> - Either filePath **or** activeEditorId` to locate the note in context. | Performs atomic writes: appends, prepends or completely overwrites a file's contents while preserving versioning metadata. |
| obsidian_search_replace (search part) | /search?{queryParameters} | GET | - q={term} (required) <br> - `useRegex={true|false} <br> - folderPath=/path/to/folder` (optional filter) | Returns a list of file paths/snippets that match the search term. The response is used by the subsequent update step to know which files to modify. |
| obsidian_global_search | /search?{queryParameters} | GET | - Same parameters as above, plus pagination: page, pageSize. <br> - Optional filters like modifiedSince, createdBefore. | Performs a vault‑wide search (all notes) and returns a paginated result set. If the live API fails it falls back to a cached index. |
| obsidian_list_notes | /vault/{vaultId}/folders/{dirPath} or /vault/{vaultId}/root | GET | - fileExtensionFilter={.md,.pdf,…} <br> - nameRegexFilter=<regex> (optional) | Returns a directory‑tree JSON representing files/folders under the given path, optionally filtered by extension or regex pattern. |
| obsidian_manage_frontmatter | /vault/{vaultId}/files/{filePath} (with metadata flag) | GET, PATCH, DELETE | - `operation={get|set|delete} <br> - For set: keyName=<metadataKey> and value=<newValue> <br> - For delete`: no extra fields needed. | Reads or updates YAML front‑matter blocks without touching note content. Allows adding, removing, or listing metadata keys (license, author, etc.). |
| obsidian_manage_tags | /vault/{vaultId}/files/{filePath} (combined with tag ops) | GET, POST, PATCH | - `operation={add|remove|list} <br> - tags=<comma‑separated list>` | Mutates both the YAML block and inline #tag references, keeping structural tags (#my-tag) synchronized with the metadata field. |
| obsidian_delete_note | /vault/{vaultId}/files/{filePath} | DELETE | - Either explicit file path or an identifier like daily:2024-01-25. | Permanently removes a note from the vault and triggers cache invalidation so all endpoints stay in sync. |

> **Note on Base URL:** All calls go through the Local REST API's root endpoint `<obsidian‑base-url>/vault/{vaultId}`. The `{vaultId}` segment is often omitted if you use the "active workspace" identifier, which resolves to the currently opened vault.

---

## 3. Example cURL Snippets (From test/ Folder)

| Endpoint | Sample Request |
|----------|----------------|
| Read a note | `curl -X GET "http://localhost:3333/vault/0/files/README.md?plaintext=true&includeStat=true"` |
| Update by appending | `curl -X POST "http://localhost:3333/vault/0/files/Example.md" -d '{"content":"Appended text","mode":"append"}'` (JSON body) |
| Search for a term | `curl -G "http://localhost:3333/search?q=Obsidian+MCP&useRegex=false"` |
| Get front‑matter key | `curl -X GET "http://localhost:3333/vault/0/files/Note.md?operation=get&keyName=author"` |

These snippets illustrate the exact request shapes you'll need to send from any MCP tool implementation (or from a script that calls the REST API directly).

---

## 4. Direct REST API vs MCP Server

### When to Use Direct REST API (This Skill)

Use the direct Obsidian Local REST API (documented in `api_endpoints.md` and `examples.md`) when:
- Working with simple CRUD operations on notes
- Making targeted updates with PATCH operations
- Managing frontmatter and tags directly
- You need full control over HTTP requests
- Working outside of MCP server context

### When to Use MCP Server

The MCP server provides an abstraction layer that may be useful when:
- Using a full MCP-compatible framework
- Need orchestrated multi-step operations
- Want built-in caching and error handling
- Working within an MCP ecosystem

For most direct AI agent interactions with Obsidian, the REST API approach (this skill) is simpler and more transparent.

---

## 5. REST API Equivalents

For reference, here's how MCP operations map to the REST API endpoints documented in this skill:

| MCP Operation | REST API Equivalent |
|---------------|---------------------|
| obsidian_read_note | `GET /vault/{filename}` with Accept headers |
| obsidian_update_note (append) | `POST /vault/{filename}` |
| obsidian_update_note (overwrite) | `PUT /vault/{filename}` |
| obsidian_update_note (targeted) | `PATCH /vault/{filename}` |
| obsidian_delete_note | `DELETE /vault/{filename}` |
| obsidian_list_notes | `GET /vault/` or `GET /vault/{directory}/` |
| obsidian_manage_frontmatter | `PATCH /vault/{filename}` with frontmatter target |
| obsidian_manage_tags | `PATCH /vault/{filename}` with frontmatter tags field |
| obsidian_global_search | **Use omnisearch tool instead** |

---

## TL;DR

- The MCP server defines eight primary tools (read, update, search/replace, global search, list notes, front‑matter, tags, delete).  
- Each tool directly maps to a specific REST endpoint pattern under `/vault/{vaultId}/...`.  
- All endpoints operate via HTTP GET/POST/PATCH/DELETE and often require query parameters (plaintext, mode, q, etc.) or JSON payloads.  
- **For direct REST API usage, refer to `api_endpoints.md` and `examples.md` in this skill.**
- **For search operations, use the `omnisearch` custom tool.**
- The repository already supplies test‑curl examples; those can be copied into your research folder for quick reference.
