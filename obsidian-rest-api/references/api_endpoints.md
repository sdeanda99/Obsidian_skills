# API Endpoints Reference

Comprehensive reference for all Obsidian Local REST API endpoints.

## Table of Contents

- [Authentication](#authentication)
- [System Endpoints](#system-endpoints)
- [Vault File Operations](#vault-file-operations)
- [Vault Directory Operations](#vault-directory-operations)
- [Active File Operations](#active-file-operations)
- [Periodic Notes](#periodic-notes)
- [Search Operations](#search-operations)
- [Commands](#commands)
- [Open Operations](#open-operations)

## Authentication

All endpoints (except `GET /`) require Bearer token authentication.

**Header Format:**
```
Authorization: Bearer YOUR_API_KEY
```

**Environment Variable:**
```bash
obsidian_api_keys=YOUR_API_KEY
```

**Usage in curl:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" ...
```

## System Endpoints

### GET /

Get server status and authentication information.

**Authentication:** Not required

**Response:**
```json
{
  "authenticated": true,
  "ok": "OK",
  "service": "Obsidian Local REST API",
  "versions": {
    "obsidian": "1.0.0",
    "self": "1.5.0"
  }
}
```

**Example:**
```bash
curl http://localhost:27123/
```

### GET /openapi.yaml

Returns the OpenAPI specification for the API.

**Authentication:** Required

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/openapi.yaml
```

### GET /obsidian-local-rest-api.crt

Returns the self-signed SSL certificate used by the HTTPS server.

**Authentication:** Required

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/obsidian-local-rest-api.crt
```

## Vault File Operations

### GET /vault/{filename}

Read the content of a specific file.

**Path Parameter:**
- `filename` - Path to file relative to vault root (e.g., `folder/note.md`)

**Headers:**
- `Authorization` - Bearer token (required)
- `Accept` - Response format (optional)
  - `text/markdown` - Raw markdown (default)
  - `application/vnd.olrapi.note+json` - JSON with metadata
  - `application/vnd.olrapi.document-map+json` - Document structure

**Response (text/markdown):**
```markdown
# My Note

Content here
```

**Response (application/vnd.olrapi.note+json):**
```json
{
  "content": "# My Note\n\nContent here",
  "path": "folder/note.md",
  "frontmatter": {
    "title": "My Note",
    "tags": ["example"]
  },
  "tags": ["example"],
  "stat": {
    "ctime": 1640000000000,
    "mtime": 1640100000000,
    "size": 1024
  }
}
```

**Response (application/vnd.olrapi.document-map+json):**
```json
{
  "headings": ["# Heading 1", "## Heading 2"],
  "blocks": ["^blockref1", "^blockref2"],
  "frontmatterFields": ["title", "tags", "date"]
}
```

**Status Codes:**
- `200` - Success
- `404` - File not found

**Examples:**
```bash
# Get raw markdown
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md

# Get with metadata
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.note+json" \
     http://localhost:27123/vault/MyNote.md

# Get document map
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Accept: application/vnd.olrapi.document-map+json" \
     http://localhost:27123/vault/MyNote.md
```

### PUT /vault/{filename}

Create a new file or completely replace an existing file.

**Path Parameter:**
- `filename` - Path to file relative to vault root

**Headers:**
- `Authorization` - Bearer token (required)
- `Content-Type` - Content type (required)
  - `text/markdown` - Markdown content
  - `*/*` - Any content type

**Request Body:**
The content for the file (markdown text).

**Status Codes:**
- `204` - Success (created or updated)
- `400` - Bad request (invalid filename or content type)
- `405` - Path references a directory

**Example:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# New Note\n\nContent here" \
     http://localhost:27123/vault/NewNote.md
```

### POST /vault/{filename}

Append content to an existing file. Creates an empty file if it doesn't exist.

**Path Parameter:**
- `filename` - Path to file relative to vault root

**Headers:**
- `Authorization` - Bearer token (required)
- `Content-Type` - `text/markdown` (required)

**Request Body:**
The content to append.

**Status Codes:**
- `204` - Success
- `400` - Bad request
- `405` - Path references a directory

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "\n\n## New Section\n\nAppended content" \
     http://localhost:27123/vault/MyNote.md
```

### PATCH /vault/{filename}

Partially update content relative to a heading, block, or frontmatter field.

**Path Parameter:**
- `filename` - Path to file relative to vault root

**Headers:**
- `Authorization` - Bearer token (required)
- `Operation` - Operation to perform (required)
  - `append` - Add after target
  - `prepend` - Add before target
  - `replace` - Replace target
- `Target-Type` - Type of target (required)
  - `heading` - Target a heading
  - `block` - Target a block reference
  - `frontmatter` - Target a frontmatter field
- `Target` - Target identifier (required)
  - For headings: Use `::` delimiter for nested (e.g., `Heading 1::Subheading 1:1`)
  - For blocks: Block reference ID (e.g., `blockref1`)
  - For frontmatter: Field name (e.g., `title`)
- `Target-Delimiter` - Delimiter for nested targets (optional, default: `::`)
- `Trim-Target-Whitespace` - Trim whitespace from target (optional, default: `false`)
- `Content-Type` - Content type (optional)
  - `text/markdown` - Markdown content (default)
  - `application/json` - JSON data (useful for frontmatter)

**Request Body:**
Content to insert or replace.

**Status Codes:**
- `200` - Success
- `400` - Bad request (invalid operation, target not found)
- `404` - File not found
- `405` - Path references a directory

**Examples:**
```bash
# Append under a heading
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: My Heading" \
     -d "\n\nNew content under heading" \
     http://localhost:27123/vault/MyNote.md

# Replace frontmatter field
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: replace" \
     -H "Target-Type: frontmatter" \
     -H "Target: status" \
     -H "Content-Type: application/json" \
     -d '"completed"' \
     http://localhost:27123/vault/MyNote.md

# Append to block reference
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: block" \
     -H "Target: myblock" \
     -d "\n\nAppended to block" \
     http://localhost:27123/vault/MyNote.md
```

### DELETE /vault/{filename}

Delete a file from the vault.

**Path Parameter:**
- `filename` - Path to file relative to vault root

**Headers:**
- `Authorization` - Bearer token (required)

**Status Codes:**
- `204` - Success
- `404` - File not found
- `405` - Path references a directory

**Example:**
```bash
curl -X DELETE \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyNote.md
```

## Vault Directory Operations

### GET /vault/

List files in the vault root directory.

**Headers:**
- `Authorization` - Bearer token (required)

**Response:**
```json
{
  "files": [
    "note1.md",
    "note2.md",
    "folder/"
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Directory not found

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/
```

### GET /vault/{pathToDirectory}/

List files in a specific directory.

**Path Parameter:**
- `pathToDirectory` - Path to directory relative to vault root

**Headers:**
- `Authorization` - Bearer token (required)

**Response:**
```json
{
  "files": [
    "document.md",
    "subfolder/"
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Directory not found

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/vault/MyFolder/
```

## Active File Operations

All operations that work on vault files also work on the currently active file using the `/active/` endpoint.

### GET /active/

Read the currently active file in Obsidian.

**Headers:**
- `Authorization` - Bearer token (required)
- `Accept` - Response format (optional, same as `GET /vault/{filename}`)

**Response:** Same as `GET /vault/{filename}`

**Status Codes:**
- `200` - Success
- `404` - No active file

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/active/
```

### PUT /active/

Overwrite the currently active file.

**Headers & Body:** Same as `PUT /vault/{filename}`

**Example:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# Updated Content" \
     http://localhost:27123/active/
```

### POST /active/

Append to the currently active file.

**Headers & Body:** Same as `POST /vault/{filename}`

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "\n\nAppended content" \
     http://localhost:27123/active/
```

### PATCH /active/

Partially update the currently active file.

**Headers & Body:** Same as `PATCH /vault/{filename}`

**Example:**
```bash
curl -X PATCH \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Operation: append" \
     -H "Target-Type: heading" \
     -H "Target: My Heading" \
     -d "\n\nNew content" \
     http://localhost:27123/active/
```

### DELETE /active/

Delete the currently active file.

**Headers:** Same as `DELETE /vault/{filename}`

**Example:**
```bash
curl -X DELETE \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/active/
```

## Periodic Notes

Periodic notes support daily, weekly, monthly, quarterly, and yearly notes.

### GET /periodic/{period}/

Get the current periodic note for the specified period.

**Path Parameter:**
- `period` - Note period (required)
  - `daily`, `weekly`, `monthly`, `quarterly`, `yearly`

**Headers:**
- `Authorization` - Bearer token (required)
- `Accept` - Response format (optional, same as `GET /vault/{filename}`)

**Status Codes:**
- `200` - Success
- `404` - File not found

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/periodic/daily/
```

### PUT /periodic/{period}/

Create or overwrite the current periodic note.

**Path Parameter:** Same as `GET /periodic/{period}/`

**Headers & Body:** Same as `PUT /vault/{filename}`

**Example:**
```bash
curl -X PUT \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "# Today's Note" \
     http://localhost:27123/periodic/daily/
```

### POST /periodic/{period}/

Append to the current periodic note. Creates the note if it doesn't exist.

**Path Parameter:** Same as `GET /periodic/{period}/`

**Headers & Body:** Same as `POST /vault/{filename}`

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: text/markdown" \
     -d "\n\n- New task" \
     http://localhost:27123/periodic/daily/
```

### PATCH /periodic/{period}/

Partially update the current periodic note.

**Path Parameter:** Same as `GET /periodic/{period}/`

**Headers & Body:** Same as `PATCH /vault/{filename}`

### DELETE /periodic/{period}/

Delete the current periodic note.

**Path Parameter:** Same as `GET /periodic/{period}/`

**Headers:** Same as `DELETE /vault/{filename}`

### GET /periodic/{period}/{year}/{month}/{day}/

Get a specific periodic note by date.

**Path Parameters:**
- `period` - Note period (`daily`, `weekly`, `monthly`, `quarterly`, `yearly`)
- `year` - Year (e.g., `2026`)
- `month` - Month (1-12)
- `day` - Day (1-31)

**Headers:** Same as `GET /vault/{filename}`

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/periodic/daily/2026/01/25/
```

### PUT /periodic/{period}/{year}/{month}/{day}/

Create or overwrite a periodic note for a specific date.

**Path Parameters:** Same as `GET /periodic/{period}/{year}/{month}/{day}/`

**Headers & Body:** Same as `PUT /vault/{filename}`

### POST /periodic/{period}/{year}/{month}/{day}/

Append to a periodic note for a specific date. Creates if needed.

**Path Parameters:** Same as `GET /periodic/{period}/{year}/{month}/{day}/`

**Headers & Body:** Same as `POST /vault/{filename}`

### PATCH /periodic/{period}/{year}/{month}/{day}/

Partially update a periodic note for a specific date.

**Path Parameters:** Same as `GET /periodic/{period}/{year}/{month}/{day}/`

**Headers & Body:** Same as `PATCH /vault/{filename}`

### DELETE /periodic/{period}/{year}/{month}/{day}/

Delete a periodic note for a specific date.

**Path Parameters:** Same as `GET /periodic/{period}/{year}/{month}/{day}/`

**Headers:** Same as `DELETE /vault/{filename}`

## Search Operations

**Note:** For search operations, prefer using the `omnisearch` custom tool instead of these API endpoints. The omnisearch tool provides better search functionality.

### POST /search/

Advanced search using Dataview DQL or JsonLogic queries.

**Headers:**
- `Authorization` - Bearer token (required)
- `Content-Type` - Query format (required)
  - `application/vnd.olrapi.dataview.dql+txt` - Dataview query
  - `application/vnd.olrapi.jsonlogic+json` - JsonLogic query

**Request Body (Dataview DQL):**
```
TABLE
  time-played AS "Time Played",
  rating AS "Rating"
FROM #game
SORT rating DESC
```

**Request Body (JsonLogic):**
```json
{
  "==": [
    {"var": "frontmatter.status"},
    "completed"
  ]
}
```

**Response:**
```json
[
  {
    "filename": "path/to/note.md",
    "result": { /* query result */ }
  }
]
```

**Status Codes:**
- `200` - Success
- `400` - Bad request (invalid query or Content-Type)

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     -H "Content-Type: application/vnd.olrapi.jsonlogic+json" \
     -d '{"in": ["mytag", {"var": "tags"}]}' \
     http://localhost:27123/search/
```

### POST /search/simple/

Simple text search across vault.

**Query Parameters:**
- `query` - Search query (required)
- `contextLength` - Context characters around match (optional, default: 100)

**Headers:**
- `Authorization` - Bearer token (required)

**Response:**
```json
[
  {
    "filename": "note.md",
    "score": 0.95,
    "matches": [
      {
        "match": {"start": 10, "end": 20},
        "context": "...text before match text after..."
      }
    ]
  }
]
```

**Status Codes:**
- `200` - Success

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     "http://localhost:27123/search/simple/?query=my+search&contextLength=150"
```

## Commands

### GET /commands/

Get a list of all available Obsidian commands.

**Headers:**
- `Authorization` - Bearer token (required)

**Response:**
```json
{
  "commands": [
    {
      "id": "global-search:open",
      "name": "Search: Search in all files"
    },
    {
      "id": "graph:open",
      "name": "Graph view: Open graph view"
    }
  ]
}
```

**Status Codes:**
- `200` - Success

**Example:**
```bash
curl -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/commands/
```

### POST /commands/{commandId}/

Execute a specific Obsidian command.

**Path Parameter:**
- `commandId` - The command ID (e.g., `global-search:open`)

**Headers:**
- `Authorization` - Bearer token (required)

**Status Codes:**
- `204` - Success
- `404` - Command not found

**Example:**
```bash
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/commands/graph:open/
```

## Open Operations

### POST /open/{filename}

Open a file in the Obsidian UI.

**Path Parameter:**
- `filename` - Path to file relative to vault root

**Query Parameters:**
- `newLeaf` - Open in a new pane (optional, boolean)

**Headers:**
- `Authorization` - Bearer token (required)

**Status Codes:**
- `200` - Success

**Note:** Obsidian will create the file if it doesn't exist.

**Examples:**
```bash
# Open in current pane
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     http://localhost:27123/open/MyNote.md

# Open in new pane
curl -X POST \
     -H "Authorization: Bearer ${obsidian_api_keys}" \
     "http://localhost:27123/open/MyNote.md?newLeaf=true"
```

## Response Schemas

### NoteJson Schema

Returned when using `Accept: application/vnd.olrapi.note+json`:

```json
{
  "content": "string - full markdown content",
  "path": "string - file path relative to vault root",
  "frontmatter": {
    /* object - parsed YAML frontmatter */
  },
  "tags": ["string"], // array of tags found in note
  "stat": {
    "ctime": 1640000000000, // creation time (ms since epoch)
    "mtime": 1640100000000, // modification time (ms since epoch)
    "size": 1024            // file size in bytes
  }
}
```

### Document Map Schema

Returned when using `Accept: application/vnd.olrapi.document-map+json`:

```json
{
  "headings": ["# Heading 1", "## Heading 2"],
  "blocks": ["^blockref1", "^blockref2"],
  "frontmatterFields": ["title", "tags", "date"]
}
```

### Error Schema

Returned for error responses:

```json
{
  "errorCode": 40149,
  "message": "A brief description of the error."
}
```

## Common HTTP Status Codes

- `200` - OK (successful GET request)
- `204` - No Content (successful PUT/POST/PATCH/DELETE)
- `400` - Bad Request (invalid parameters or content)
- `401` - Unauthorized (invalid or missing API key)
- `404` - Not Found (file or resource doesn't exist)
- `405` - Method Not Allowed (operation not valid for resource type)

## URL Encoding

- Target values in PATCH operations should be URL-encoded if they contain special characters
- Non-ASCII characters **must** be URL-encoded
- Use standard URL encoding for spaces and special characters in paths

**Example:**
```bash
# Encoding "My Heading" for PATCH Target header
curl -X PATCH \
     -H "Target: My%20Heading" \
     ...
```
