# CLI Command Reference

Condensed reference for Obsidian CLI commands used in vault operations. For the full CLI
documentation, run `obsidian help` or see https://obsidian.md/help/cli.

## File Operations

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian create` | `name`, `path`, `content`, `template`, `overwrite` | Dirs created automatically |
| `obsidian read` | `file`, `path` | Defaults to active file |
| `obsidian append` | `content` (required), `file`, `path`, `inline` | `inline` skips leading newline |
| `obsidian prepend` | `content` (required), `file`, `path` | Inserts after frontmatter |
| `obsidian delete` | `file`, `path`, `permanent` | Trash by default |
| `obsidian move` | `to` (required), `file`, `path` | Updates wikilinks automatically |
| `obsidian rename` | `name` (required), `file`, `path` | Extension preserved if omitted |
| `obsidian files` | `folder`, `ext`, `total` | Lists all matching files |
| `obsidian file` | `file`, `path` | Shows file metadata |

## Properties (Frontmatter)

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian property:set` | `name`, `value`, `type`, `file`, `path` | Types: text\|list\|number\|checkbox\|date\|datetime |
| `obsidian property:read` | `name`, `file`, `path` | Returns raw value |
| `obsidian property:remove` | `name`, `file`, `path` | Removes field entirely |
| `obsidian properties` | `file`, `path`, `format` | `format=json` for structured output |

## Tags

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian tags` | `file`, `path`, `sort`, `counts`, `format` | `format=json\|tsv\|csv` |
| `obsidian tag` | `name` (required), `total`, `verbose` | Info on a specific tag |

## Tasks

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian tasks` | `file`, `path`, `done`, `todo`, `verbose`, `format` | `verbose` adds line numbers |
| `obsidian task` | `file`, `path`, `line`, `done`, `todo`, `toggle` | Line number required |

## Links

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian backlinks` | `file`, `path`, `format` | Files that link to target |
| `obsidian orphans` | (none) | Files with no incoming links |
| `obsidian unresolved` | `verbose`, `format` | Broken wikilinks |

## Daily Notes

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian daily` | `paneType` | Opens today's note |
| `obsidian daily:read` | (none) | Returns content |
| `obsidian daily:append` | `content` (required), `open` | Appends to today |
| `obsidian daily:prepend` | `content` (required), `open` | Prepends to today |
| `obsidian daily:path` | (none) | Returns file path |

## Escape Hatch

| Command | Key Parameters | Notes |
|---|---|---|
| `obsidian eval` | `code` (required) | Full access to `app` object |

## Parameter Notes

- `file=<name>` — wikilink-style resolution (no path, no extension)
- `path=<path>` — full path from vault root, e.g. `Projects/Note.md`
- `vault=<name>` — must be first parameter before the command
- Content with spaces: wrap in quotes — `content="Hello world"`
- Newlines in content: use `\n` — `content="Line 1\nLine 2"`
- `format=json` — use wherever available for structured output
