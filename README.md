# tool-to-agent-retrieval-mcp

An MCP server that selects the best-suited downstream agent for a natural language query
and forwards a tool call to it. Distributed via `uvx`.

## Usage

Add to Claude Desktop (`claude_desktop_config.json`) or Claude Code (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "tool-to-agent-retrieval-mcp": {
      "command": "uvx",
      "args": ["tool-to-agent-retrieval-mcp"]
    }
  }
}
```

Configure your agent corpus in `.mcp-corpus.json` (or `$MCP_CORPUS_PATH`). The server
exposes three tools: `search_tools`, `get_tool_details`, and `invoke_tool`.

### Remote MCP Server Support

The corpus now supports **remote MCP servers** via SSE and Streamable HTTP transports,
in addition to local stdio-based servers:

```json
{
  "mcpServers": {
    "aws-knowledge": {
      "description": "AWS documentation, regional availability, and best practices",
      "url": "https://knowledge-mcp.global.api.aws",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer ${AWS_API_TOKEN}"
      },
      "tools": [
        {
          "name": "search_documentation",
          "description": "Search AWS documentation"
        },
        {
          "name": "read_documentation",
          "description": "Read full AWS documentation pages"
        }
      ]
    },
    "notion": {
      "description": "Notion workspace — pages, databases, comments",
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": {
        "OPENAPI_MCP_HEADERS": "{\"Authorization\":\"Bearer ${NOTION_TOKEN}\",\"Notion-Version\":\"2022-06-28\"}"
      }
    }
  }
}
```

### Corpus Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | stdio only | Command to spawn for stdio transport |
| `args` | string[] | - | Arguments passed to `command` |
| `env` | object | - | Environment variables (supports `${VAR}` references) |
| `url` | string | SSE/HTTP | URL for remote MCP servers |
| `transport` | string | - | `"stdio"`, `"sse"`, or `"streamable-http"` (auto-detected by default) |
| `headers` | object | - | HTTP headers for remote connections (supports `${VAR}` references) |
| `description` | string | Yes | Agent description (used for retrieval) |
| `tools` | array[] | Yes | List of tools exposed by the agent |

**Transport auto-detection:** If `command` is present, defaults to `"stdio"`. If only `url` is present, defaults to `"sse"`.

## Algorithm

The retrieval algorithm is based on:

> Lumer, S., et al. (2025). **Tool-to-Agent Retrieval: Bridging Tools and Agents for
> Scalable LLM Multi-Agent Systems**. PricewaterhouseCoopers.
> arXiv:2511.01854v2.

A unified catalog C = CT ∪ CA (tool corpus + agent corpus) is built offline and searched
at query time using Algorithm 1: top-N candidates are ranked by similarity, then
deduplicated to return the top-K unique owner agents.

## Development

```
uv run pytest tests/pytest/
```
