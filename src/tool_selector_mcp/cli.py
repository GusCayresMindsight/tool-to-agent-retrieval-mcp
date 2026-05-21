"""Command-line entry point: ``uvx tool-selector-mcp`` -> this ``main``."""

from __future__ import annotations

import dataclasses
import sys

from mcp.server.fastmcp import FastMCP

from .corpus import CorpusError, load_corpus, resolve_corpus_path
from .server import ToolSelectorServer, UnknownToolError


def build_server() -> ToolSelectorServer:
    """Load the corpus and return a configured ``ToolSelectorServer``."""
    path = resolve_corpus_path()
    corpus = load_corpus(path)
    return ToolSelectorServer(corpus)


def main(argv: list[str] | None = None) -> int:
    try:
        ts = build_server()
    except CorpusError as exc:
        print(f"tool-selector-mcp: {exc}", file=sys.stderr)
        return 1
    app = FastMCP("tool-selector-mcp")

    @app.tool()
    def search_tools(query: str, k: int = 1) -> list[dict]:
        """Return up to k agents/tools ranked by relevance to the query."""
        return [dataclasses.asdict(h) for h in ts.search_tools(query, k)]

    @app.tool()
    def get_tool_details(tool_ids: list[str]) -> list[dict]:
        """Return full input schemas for the given tool IDs (format: agent_id.tool_name)."""
        try:
            return [dataclasses.asdict(d) for d in ts.get_tool_details(tool_ids)]
        except UnknownToolError as exc:
            return [{"error": str(exc)}]

    @app.tool()
    def invoke_tool(
        tool: str,
        arguments: dict | None = None,
        server: str | None = None,
    ) -> dict:
        """Invoke a tool on its owning downstream agent."""
        try:
            return {"result": ts.invoke_tool(tool, arguments, server=server)}
        except (UnknownToolError, RuntimeError) as exc:
            return {"error": str(exc)}

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
