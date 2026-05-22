# tool-selector-mcp

An MCP server that selects the best-suited downstream agent for a natural language query
and forwards a tool call to it. Distributed via `uvx`.

## Usage

Add to Claude Desktop (`claude_desktop_config.json`) or Claude Code (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "tool-selector-mcp": {
      "command": "uvx",
      "args": ["tool-selector-mcp"]
    }
  }
}
```

Configure your agent corpus in `.mcp-corpus.json` (or `$MCP_CORPUS_PATH`). The server
exposes three tools: `search_tools`, `get_tool_details`, and `invoke_tool`.

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
