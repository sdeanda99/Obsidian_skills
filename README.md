# Obsidian Skills for OpenCode

OpenCode skills and tools for seamless Obsidian integration. This repository provides AI agents with the ability to interact with your Obsidian vault through the REST API and search capabilities.

## Features

- **Obsidian REST API Skill** - Full CRUD operations for notes with metadata management
- **Omnisearch Custom Tool** - Fast, fuzzy vault search with result excerpts
- **Comprehensive Documentation** - API references, authentication guides, and practical examples
- **MCP Integration Research** - Notes on Model Context Protocol server integration

## Prerequisites

### Required Software

- **Obsidian** (latest version recommended)
- **Node.js** 16+ (for TypeScript tools)
- **Python** 3.10+ (for any Python-based utilities)

### Required Obsidian Plugins

1. **Local REST API** - For REST API skill functionality
   - Install from Community Plugins
   - Enable the plugin
   - Copy your API key from plugin settings

2. **Omnisearch** - For search tool functionality
   - Install from Community Plugins
   - Enable HTTP Server in Omnisearch settings (runs on port 51361)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sdeanda99/Obsidian_skills.git
cd Obsidian_skills
```

### 2. Install Python Dependencies

**Option A: Using `uv` (recommended - faster)**

```bash
uv pip install -e .
```

**Option B: Using standard `pip`**

```bash
pip install -r requirements.txt
```

### 3. Configure API Authentication

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Obsidian REST API key:

```bash
obsidian_api_keys=YOUR_API_KEY_HERE
```

To find your API key:
1. Open Obsidian
2. Go to Settings → Community Plugins → Local REST API
3. Copy the API key shown

### 4. Deploy Skills and Tools

**For OpenCode Users:**

Copy the skill and tools to your OpenCode configuration:

```bash
# Copy the REST API skill
cp -r obsidian-rest-api ~/.claude/skills/

# Copy the Omnisearch tool
cp tools/omnisearch.ts ~/.claude/tools/
```

Restart OpenCode to load the new skill and tool.

## Quick Start

### Using the REST API Skill

The skill automatically loads when you mention Obsidian operations:

```
"Create a new note called 'Meeting Notes' with today's date"
"Update the frontmatter in my Daily Note"
"Read the content of 'Project Ideas.md'"
```

### Using the Omnisearch Tool

Search your vault for specific content:

```
"Search my vault for 'machine learning' notes"
"Find all notes mentioning 'project deadline'"
```

### Manual API Testing

Test the REST API connection:

```bash
# Load API key
export $(cat .env | xargs)

# Test connection
curl -H "Authorization: Bearer ${obsidian_api_keys}" http://localhost:27123/

# Create a note
curl -X PUT \
  -H "Authorization: Bearer ${obsidian_api_keys}" \
  -H "Content-Type: text/markdown" \
  -d "# My First Note\n\nCreated via API!" \
  "http://localhost:27123/vault/My%20First%20Note.md"
```

## Available Tools & Skills

### 1. Obsidian REST API Skill

**Location:** `obsidian-rest-api/`

**Capabilities:**
- Create notes with optional front-matter
- Read note content and metadata
- Update notes (append, overwrite, or targeted patches)
- Delete notes
- Manage tags and front-matter fields
- Work with the currently active file

**Documentation:**
- `obsidian-rest-api/SKILL.md` - Main skill guide
- `obsidian-rest-api/references/api_endpoints.md` - Complete endpoint reference
- `obsidian-rest-api/references/authentication.md` - Setup guide
- `obsidian-rest-api/references/examples.md` - Practical examples

### 2. Omnisearch Custom Tool

**Location:** `tools/omnisearch.ts`

**Capabilities:**
- Full-text search across your vault
- Fuzzy matching for flexible queries
- Returns excerpts with context
- Configurable result limits

**Documentation:**
- `docs/OMNISEARCH_TOOL.md` - Comprehensive tool guide
- `docs/omnisearch.md` - Quick reference

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Obsidian REST API Key
obsidian_api_keys=YOUR_API_KEY_HERE
```

### Default API Endpoints

- **REST API:** `http://localhost:27123`
- **Omnisearch:** `http://localhost:51361`

These ports are the default for the respective plugins. If you've changed them, update the tool configurations accordingly.

## Troubleshooting

### REST API Not Responding

1. **Check if Obsidian is running**
   ```bash
   ps aux | grep -i obsidian
   ```

2. **Verify Local REST API plugin is enabled**
   - Open Obsidian → Settings → Community Plugins
   - Ensure Local REST API is enabled

3. **Test connection**
   ```bash
   curl http://localhost:27123/
   ```

### Omnisearch Not Finding Results

1. **Check if HTTP server is enabled**
   - Obsidian → Settings → Omnisearch → Enable HTTP Server

2. **Verify the plugin is indexing**
   - Try searching in Obsidian UI first
   - Trigger a re-index if needed

3. **Test the endpoint**
   ```bash
   curl "http://localhost:51361/search?q=test"
   ```

### API Key Issues

- Ensure no extra spaces in `.env` file
- Verify the key is correctly copied from plugin settings
- Check that `.env` is in the project root
- Make sure `.env` is loaded: `export $(cat .env | xargs)`

## Documentation

Additional documentation can be found in:

- `docs/` - General documentation and guides
- `obsidian-rest-api/references/` - Detailed API references
- `docs/rest-api-integration/` - Integration notes and research

## Contributing

Contributions are welcome! Please ensure:

1. Code follows existing style conventions
2. Documentation is updated for new features
3. Skills include clear "when to use" descriptions
4. Tools have comprehensive error handling

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Obsidian](https://obsidian.md/) - The knowledge base application
- [Local REST API Plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) - REST API functionality
- [Omnisearch Plugin](https://github.com/scambier/obsidian-omnisearch) - Search capabilities

## Version

**Current Version:** 1.0.0

---

**Author:** Sebastian De Anda  
**Repository:** https://github.com/sdeanda99/Obsidian_skills
