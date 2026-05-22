"""Command-line entry point: ``uvx tool-selector-mcp`` -> this ``main``."""

from __future__ import annotations

import dataclasses
import os
import sys

from mcp.server.fastmcp import FastMCP

from .corpus import CorpusError, load_corpus, resolve_corpus_path
from .embeddings import UnknownEmbeddingError, build_embedding
from .server import ToolSelectorServer, UnknownToolError, make_subprocess_launcher

DEFAULT_EMBEDDING = "token-overlap"
EMBEDDING_ENV_VAR = "TOOL_SELECTOR_EMBEDDING"


def build_server() -> ToolSelectorServer:
    """Load the corpus and return a configured ``ToolSelectorServer``.

    The active embedding is selected via the ``TOOL_SELECTOR_EMBEDDING``
    environment variable; absence falls back to the token-overlap embedding.
    """
    path = resolve_corpus_path()
    corpus = load_corpus(path)
    name = os.environ.get(EMBEDDING_ENV_VAR, DEFAULT_EMBEDDING)
    embedding = build_embedding(name)
    return ToolSelectorServer(corpus, launcher=make_subprocess_launcher(), embedding=embedding)


def main(argv: list[str] | None = None) -> int:
    try:
        ts = build_server()
    except (CorpusError, UnknownEmbeddingError) as exc:
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
    async def invoke_tool(
        tool: str,
        arguments: dict | None = None,
        server: str | None = None,
    ) -> dict:
        """Invoke a tool on its owning downstream agent."""
        try:
            result = await ts.invoke_tool_async(tool, arguments, server=server)
            return {"result": result}
        except (UnknownToolError, RuntimeError) as exc:
            return {"error": str(exc)}

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
