# Omnisearch Custom Tool

A custom tool for OpenCode that integrates with the Obsidian Omnisearch plugin via its HTTP API.

## Overview

This tool enables AI agents to search your Obsidian vault directly from OpenCode conversations. It uses the Omnisearch plugin's HTTP server to execute searches and return results with relevance scores, excerpts, and metadata.

## Features

The tool provides three operations:

1. **omnisearch_search** - Search your vault and get ranked results
2. **omnisearch_refreshIndex** - Information about index refresh (API limitation note)
3. **omnisearch_openSearch** - Open Omnisearch in Obsidian with a pre-filled query

## Installation

### Prerequisites

1. **Obsidian** must be installed and running
2. **Omnisearch plugin** must be installed in Obsidian
3. **HTTP Server must be enabled** in Omnisearch settings:
   - Open Obsidian Settings (Ctrl/Cmd + ,)
   - Navigate to Community Plugins → Omnisearch
   - Enable "HTTP Server"

### Tool Installation

The tool file is located at:
```
.opencode/tools/omnisearch.ts
```

OpenCode automatically loads tools from this directory. No additional installation steps are needed.

## Usage

### Search Your Vault

Ask the AI agent to search your Obsidian vault:

```
"Search my Obsidian vault for notes about machine learning"
```

The agent will use the `omnisearch_search` tool with your query and return formatted results.

### Advanced Search with Limits

You can control the number of results:

```
"Find the top 5 notes about Python in my vault"
```

### Open Omnisearch in Obsidian

You can also open the Omnisearch interface directly:

```
"Open Omnisearch with the query 'project planning'"
```

## API Reference

### omnisearch_search

Search the Obsidian vault using Omnisearch.

**Arguments:**
- `query` (string, required) - The search query to execute
- `limit` (number, optional) - Maximum results to return (default: 10)

**Returns:**
```json
{
  "query": "search term",
  "totalResults": 25,
  "returnedResults": 10,
  "results": [
    {
      "path": "folder/note.md",
      "basename": "note",
      "score": 142,
      "excerpt": "...matched text excerpt...",
      "foundWords": ["search", "term"],
      "vault": "MyVault"
    }
  ]
}
```

**Example Usage:**
```typescript
// Agent calls:
omnisearch_search({ 
  query: "machine learning", 
  limit: 5 
})
```

### omnisearch_openSearch

Open Omnisearch in Obsidian with an optional pre-filled query.

**Arguments:**
- `query` (string, optional) - Query to pre-fill in Omnisearch

**Returns:**
```json
{
  "message": "Opened Omnisearch in Obsidian",
  "url": "obsidian://omnisearch?query=...",
  "query": "your query"
}
```

**Example Usage:**
```typescript
// Agent calls:
omnisearch_openSearch({ 
  query: "todo items" 
})
```

## Response Format

### Successful Search

```json
{
  "query": "machine learning",
  "totalResults": 15,
  "returnedResults": 10,
  "results": [
    {
      "path": "AI/machine-learning-basics.md",
      "basename": "machine-learning-basics",
      "score": 250,
      "excerpt": "Machine learning is a subset of artificial intelligence...",
      "foundWords": ["machine", "learning"],
      "vault": "Knowledge"
    }
  ]
}
```

### Error Responses

**Connection Error (Obsidian not running):**
```json
{
  "error": "Cannot connect to Omnisearch API",
  "details": "Make sure Obsidian is running and the Omnisearch HTTP server is enabled in settings",
  "originalError": "fetch failed"
}
```

**HTTP Server Disabled:**
```json
{
  "error": "Cannot connect to Omnisearch API",
  "details": "Make sure Obsidian is running and the Omnisearch HTTP server is enabled in settings (Preferences → Omnisearch → Enable HTTP server)",
  "status": 404
}
```

## Troubleshooting

### "Cannot connect to Omnisearch API"

**Cause:** Obsidian is not running, or the HTTP server is disabled.

**Solutions:**
1. Start Obsidian
2. Check that Omnisearch plugin is installed
3. Enable HTTP server in Omnisearch settings:
   - Settings → Community Plugins → Omnisearch
   - Toggle "Enable HTTP server"

### "API request failed"

**Cause:** HTTP request succeeded but server returned an error.

**Solutions:**
1. Check Obsidian console for errors (Ctrl+Shift+I / Cmd+Option+I)
2. Verify Omnisearch plugin is up to date
3. Try restarting Obsidian

### Tool Not Found

**Cause:** OpenCode hasn't loaded the tool.

**Solutions:**
1. Verify file exists at `.opencode/tools/omnisearch.ts`
2. Check file permissions (should be readable)
3. Restart OpenCode
4. Check for syntax errors: `bun check .opencode/tools/omnisearch.ts`

## Technical Details

### Architecture

```
┌─────────────┐           ┌──────────────┐
│   OpenCode  │           │   Obsidian   │
│   Agent     │           │              │
└──────┬──────┘           └──────┬───────┘
       │                         │
       │ Tool Call               │
       │ omnisearch_search       │
       ▼                         ▼
┌──────────────┐          ┌─────────────┐
│ omnisearch.ts│──HTTP───▶│ Omnisearch  │
│    Tool      │          │ HTTP Server │
└──────────────┘          └─────────────┘
                          localhost:51361
```

### HTTP API Endpoints

The tool uses Omnisearch's HTTP API:

- **Search:** `GET http://localhost:51361/search?q=<query>`
- **Port:** 51361 (fixed)
- **Scope:** localhost only (not accessible outside your machine)
- **Lifecycle:** Started/stopped with Obsidian

### URL Scheme

For opening Omnisearch directly:
- **Scheme:** `obsidian://omnisearch?query=<query>`
- **Behavior:** Switches focus to Obsidian and opens Omnisearch with query

## Limitations

1. **HTTP Server Only:** The tool can only access functionality exposed by the HTTP API. Features like `refreshIndex` that are only available in the JavaScript API cannot be used.

2. **Local Only:** The HTTP server only accepts connections from localhost (127.0.0.1). This is a security feature.

3. **Platform-Specific URL Opening:** The `openSearch` tool uses `xdg-open` which works on Linux. On macOS, you may need to modify it to use `open`, and on Windows, use `start`.

4. **No Mobile Support:** The Omnisearch HTTP server is not available on Obsidian Mobile.

## Security Notes

- The HTTP server runs on localhost only and is not accessible from other machines
- No authentication is required (relies on localhost isolation)
- The server automatically stops when Obsidian closes
- All data stays on your local machine

## Examples

### Example 1: Quick Search

**User:** "Find notes about TypeScript in my vault"

**Agent:** Calls `omnisearch_search({ query: "TypeScript", limit: 10 })`

**Result:**
```json
{
  "query": "TypeScript",
  "totalResults": 8,
  "returnedResults": 8,
  "results": [
    {
      "path": "Programming/typescript-basics.md",
      "score": 450,
      "excerpt": "TypeScript is a typed superset of JavaScript..."
    }
  ]
}
```

### Example 2: Detailed Search with Limit

**User:** "Show me the top 3 most relevant notes about 'project planning'"

**Agent:** Calls `omnisearch_search({ query: "project planning", limit: 3 })`

**Result:** Returns the 3 highest-scoring notes.

### Example 3: Opening Omnisearch

**User:** "Open Omnisearch and search for 'meeting notes'"

**Agent:** Calls `omnisearch_openSearch({ query: "meeting notes" })`

**Result:** Obsidian window comes to focus with Omnisearch open and "meeting notes" pre-filled.

## Contributing

To extend this tool:

1. **Add new endpoints** - If Omnisearch adds new HTTP endpoints, add corresponding functions
2. **Improve error handling** - Add more specific error cases
3. **Add result filtering** - Add options to filter by date, path, etc.
4. **Add result formatting** - Provide different output formats (markdown, plain text, etc.)

## Related Resources

- [Omnisearch Plugin](https://github.com/scambier/obsidian-omnisearch)
- [Omnisearch HTTP API Documentation](https://publish.obsidian.md/omnisearch/Public+API)
- [OpenCode Custom Tools Documentation](../opencode/custom_skills.md)

## Version History

- **v1.0.0** (2026-01-24) - Initial release
  - Search functionality via HTTP API
  - Open Omnisearch via URL scheme
  - Comprehensive error handling
