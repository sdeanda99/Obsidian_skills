import { tool } from "@opencode-ai/plugin"

/**
 * Omnisearch Custom Tool for Obsidian Integration
 * 
 * This tool searches your Obsidian vault using the Omnisearch plugin's HTTP API.
 * 
 * Prerequisites:
 * 1. Obsidian must be running
 * 2. Omnisearch plugin must be installed
 * 3. HTTP Server must be enabled in Omnisearch settings
 * 
 * The HTTP server runs on localhost:51361 and is automatically stopped when Obsidian closes.
 */

interface SearchMatch {
  match: string
  offset: number
}

interface SearchResult {
  score: number
  vault: string
  path: string
  basename: string
  foundWords: string[]
  matches: SearchMatch[]
  excerpt: string
}

export const search = tool({
  description: "Search Obsidian vault using Omnisearch plugin. Queries the local Omnisearch HTTP API to find notes matching the search query. Returns results with scores, paths, and excerpts.",
  args: {
    query: tool.schema.string().describe("Search query to execute in Obsidian vault"),
    limit: tool.schema.number().int().positive().default(10).describe("Maximum number of results to return (default: 10)")
  },
  async execute(args) {
    const { query, limit } = args
    
    try {
      // Encode the query for URL
      const encodedQuery = encodeURIComponent(query)
      const url = `http://localhost:51361/search?q=${encodedQuery}`
      
      // Make the HTTP request
      const response = await fetch(url)
      
      if (!response.ok) {
        if (response.status === 404 || response.status === 0) {
          return JSON.stringify({
            error: "Cannot connect to Omnisearch API",
            details: "Make sure Obsidian is running and the Omnisearch HTTP server is enabled in settings (Preferences → Omnisearch → Enable HTTP server)",
            status: response.status
          }, null, 2)
        }
        
        return JSON.stringify({
          error: "API request failed",
          status: response.status,
          statusText: response.statusText
        }, null, 2)
      }
      
      // Parse the response
      const results: SearchResult[] = await response.json()
      
      // Limit the results
      const limitedResults = results.slice(0, limit)
      
      // Format the results for better readability
      const formattedResults = limitedResults.map(result => ({
        path: result.path,
        basename: result.basename,
        score: Math.round(result.score),
        excerpt: result.excerpt,
        foundWords: result.foundWords,
        vault: result.vault
      }))
      
      return JSON.stringify({
        query,
        totalResults: results.length,
        returnedResults: formattedResults.length,
        results: formattedResults
      }, null, 2)
      
    } catch (error) {
      const err = error as Error
      
      // Check for connection errors
      if (err.message.includes("ECONNREFUSED") || err.message.includes("fetch failed")) {
        return JSON.stringify({
          error: "Cannot connect to Omnisearch API",
          details: "Make sure Obsidian is running and the Omnisearch HTTP server is enabled in settings",
          originalError: err.message
        }, null, 2)
      }
      
      return JSON.stringify({
        error: "Search failed",
        message: err.message,
        stack: err.stack
      }, null, 2)
    }
  }
})

export const refreshIndex = tool({
  description: "Trigger a refresh of the Omnisearch index. Note: The HTTP API doesn't expose this endpoint, so this tool uses the Obsidian URL scheme to open Omnisearch.",
  args: {},
  async execute() {
    // The HTTP API doesn't have a refresh endpoint
    // We could potentially open Obsidian and trigger a refresh via URL scheme
    return JSON.stringify({
      message: "Index refresh is not available via HTTP API",
      suggestion: "The Omnisearch HTTP API only supports search operations. To refresh the index, use the Obsidian interface or the internal JavaScript API."
    }, null, 2)
  }
})

export const openSearch = tool({
  description: "Open Omnisearch in Obsidian with an optional pre-filled query using the obsidian:// URL scheme",
  args: {
    query: tool.schema.string().optional().describe("Optional search query to pre-fill in Omnisearch")
  },
  async execute(args) {
    try {
      const { query } = args
      
      // Build the URL scheme
      let url = "obsidian://omnisearch"
      if (query) {
        url += `?query=${encodeURIComponent(query)}`
      }
      
      // Open the URL using xdg-open (Linux), open (macOS), or start (Windows)
      // We'll try xdg-open first, which works on most Linux systems
      const result = await Bun.$`xdg-open "${url}"`.quiet()
      
      return JSON.stringify({
        message: "Opened Omnisearch in Obsidian",
        url,
        query: query || "No query"
      }, null, 2)
      
    } catch (error) {
      const err = error as Error
      return JSON.stringify({
        error: "Failed to open Obsidian",
        message: err.message,
        suggestion: "Make sure Obsidian is installed and the obsidian:// URL scheme is registered"
      }, null, 2)
    }
  }
})
