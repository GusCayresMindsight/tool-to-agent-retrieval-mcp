"""Server-side logic for tool-selector-mcp.

Exposes three MCP tools to clients:

* ``search_tools(query, k=1)`` -> ranked, lightweight agent metadata.
* ``get_tool_details(tool_ids)`` -> full input schemas for selected tools.
* ``invoke_tool(tool, arguments, server=None)`` -> launches the owning
  downstream agent and forwards the call.

A downstream launch is delegated to a pluggable ``Launcher`` callable so the
core can be exercised in tests without spawning subprocesses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .corpus import Agent, Corpus, Tool
from .embeddings import Embedding
from .retrieval import search


class UnknownToolError(Exception):
    def __init__(self, tool_name: str):
        super().__init__(f"tool not found in corpus: {tool_name}")
        self.tool_name = tool_name


@dataclass(frozen=True)
class SearchHit:
    """Lightweight metadata returned by ``search_tools``.

    The full input schema is intentionally omitted; clients fetch it via
    ``get_tool_details`` once they have selected a candidate.
    """

    agent_id: str
    tool_name: str | None
    description: str


@dataclass(frozen=True)
class ToolDetail:
    agent_id: str
    tool_name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LaunchCall:
    """Record of a downstream invocation, surfaced for tests/observability."""

    agent_id: str
    command: str | None
    args: tuple[str, ...]
    env: Mapping[str, str]
    url: str | None
    transport: str
    headers: Mapping[str, str]
    tool_name: str
    arguments: Mapping[str, Any]


Launcher = Callable[[Agent, str, Mapping[str, Any]], Any]
AsyncLauncher = Callable[[Agent, str, Mapping[str, Any]], Awaitable[Any]]


def _parse_tool_id(corpus: Corpus, tool_id: str) -> tuple[Agent, Tool]:
    if "." in tool_id:
        agent_id, tool_name = tool_id.split(".", 1)
        agent = corpus.get_agent(agent_id)
        if agent is None:
            raise UnknownToolError(tool_id)
        for tool in agent.tools:
            if tool.name == tool_name:
                return agent, tool
        raise UnknownToolError(tool_id)
    found = corpus.find_tool(tool_id)
    if found is None:
        raise UnknownToolError(tool_id)
    return found


class ToolSelectorServer:
    """In-process implementation of the tool-selector-mcp behavior."""

    def __init__(
        self,
        corpus: Corpus,
        launcher: Launcher | None = None,
        *,
        rewrite_queries: bool = True,
        embedding: Embedding | None = None,
    ) -> None:
        self.corpus = corpus
        self._launcher = launcher
        self.rewrite_queries = rewrite_queries
        self.embedding = embedding

    # --- exposed MCP tools -------------------------------------------------

    def search_tools(self, query: str, k: int = 1) -> list[SearchHit]:
        results = search(
            self.corpus,
            query,
            k=k,
            rewrite=self.rewrite_queries,
            embedding=self.embedding,
        )
        hits: list[SearchHit] = []
        for r in results:
            agent = self.corpus.agents[r.agent_id]
            if r.matched_via == "tool" and r.tool_name is not None:
                tool = next(t for t in agent.tools if t.name == r.tool_name)
                hits.append(
                    SearchHit(
                        agent_id=agent.agent_id,
                        tool_name=tool.name,
                        description=tool.description,
                    )
                )
            else:
                hits.append(
                    SearchHit(
                        agent_id=agent.agent_id,
                        tool_name=None,
                        description=agent.description,
                    )
                )
        return hits

    def get_tool_details(self, tool_ids: Sequence[str]) -> list[ToolDetail]:
        details: list[ToolDetail] = []
        for tool_id in tool_ids:
            agent, tool = _parse_tool_id(self.corpus, tool_id)
            details.append(
                ToolDetail(
                    agent_id=agent.agent_id,
                    tool_name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )
            )
        return details

    def invoke_tool(
        self,
        tool: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        server: str | None = None,
    ) -> Any:
        arguments = arguments or {}
        if server is not None:
            agent = self.corpus.get_agent(server)
            if agent is None:
                raise UnknownToolError(f"{server}.{tool}")
            target_tool = next((t for t in agent.tools if t.name == tool), None)
            if target_tool is None:
                raise UnknownToolError(f"{server}.{tool}")
        else:
            found = self.corpus.find_tool(tool)
            if found is None:
                raise UnknownToolError(tool)
            agent, target_tool = found

        if self._launcher is None:
            raise RuntimeError("no launcher configured; cannot spawn downstream agent")
        return self._launcher(agent, target_tool.name, arguments)

    async def invoke_tool_async(
        self,
        tool: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        server: str | None = None,
    ) -> Any:
        """Async variant of ``invoke_tool`` — awaits an ``AsyncLauncher``."""
        arguments = arguments or {}
        if server is not None:
            agent = self.corpus.get_agent(server)
            if agent is None:
                raise UnknownToolError(f"{server}.{tool}")
            target_tool = next((t for t in agent.tools if t.name == tool), None)
            if target_tool is None:
                raise UnknownToolError(f"{server}.{tool}")
        else:
            found = self.corpus.find_tool(tool)
            if found is None:
                raise UnknownToolError(tool)
            agent, target_tool = found

        if self._launcher is None:
            raise RuntimeError("no launcher configured; cannot spawn downstream agent")
        return await self._launcher(agent, target_tool.name, arguments)


def make_subprocess_launcher() -> AsyncLauncher:
    """Return an async launcher that spawns each downstream agent as a subprocess.

    The agent's ``command`` / ``args`` / ``env`` from the corpus are used to start
    the MCP stdio server.  Credentials (GITHUB_TOKEN, etc.) are inherited from the
    parent process environment and do not need to be in the corpus.
    """

    async def launcher(agent: Agent, tool_name: str, arguments: Mapping[str, Any]) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if not agent.command:
            raise RuntimeError(f"agent {agent.agent_id} has no command (stdio transport requires one)")
        params = StdioServerParameters(
            command=agent.command,
            args=list(agent.args),
            env=dict(agent.env) if agent.env else None,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool_name, dict(arguments))

    return launcher


def make_launcher() -> AsyncLauncher:
    """Return an async launcher that connects via stdio, SSE, or streamable-http.

    The transport is determined by the agent's ``transport`` field:
    * ``stdio`` (default): spawn a subprocess.
    * ``sse``: connect to a remote SSE endpoint.
    * ``streamable-http``: connect to a remote Streamable HTTP endpoint.
    """

    async def launcher(agent: Agent, tool_name: str, arguments: Mapping[str, Any]) -> Any:
        from mcp import ClientSession

        if agent.transport == "stdio":
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            if not agent.command:
                raise RuntimeError(f"agent {agent.agent_id} has no command (stdio transport requires one)")
            params = StdioServerParameters(
                command=agent.command,
                args=list(agent.args),
                env=dict(agent.env) if agent.env else None,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, dict(arguments))

        elif agent.transport == "sse":
            from mcp.client.sse import sse_client

            if not agent.url:
                raise RuntimeError(f"agent {agent.agent_id} has no url (sse transport requires one)")
            async with sse_client(
                url=agent.url,
                headers=dict(agent.headers) if agent.headers else None,
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, dict(arguments))

        elif agent.transport == "streamable-http":
            from mcp.client.streamable_http import streamablehttp_client

            if not agent.url:
                raise RuntimeError(f"agent {agent.agent_id} has no url (streamable-http transport requires one)")
            async with streamablehttp_client(
                url=agent.url,
                headers=dict(agent.headers) if agent.headers else None,
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, dict(arguments))

        else:
            raise ValueError(f"unknown transport: {agent.transport}")

    return launcher


def make_recording_async_launcher() -> tuple[list[LaunchCall], AsyncLauncher]:
    """Return a (calls, async-launcher) pair that records every async invocation."""
    calls: list[LaunchCall] = []

    async def launcher(agent: Agent, tool_name: str, arguments: Mapping[str, Any]) -> Any:
        call = LaunchCall(
            agent_id=agent.agent_id,
            command=agent.command,
            args=tuple(agent.args),
            env=dict(agent.env),
            url=agent.url,
            transport=agent.transport,
            headers=dict(agent.headers),
            tool_name=tool_name,
            arguments=dict(arguments),
        )
        calls.append(call)
        return {
            "agent_id": agent.agent_id,
            "tool": tool_name,
            "arguments": dict(arguments),
            "ok": True,
        }

    return calls, launcher


def make_recording_launcher() -> tuple[list[LaunchCall], Launcher]:
    """Return a (calls, launcher) pair that records every invocation.

    The launcher echoes a simple synthetic response so callers can assert
    on both the launch parameters and the propagated result.
    """
    calls: list[LaunchCall] = []

    def launcher(agent: Agent, tool_name: str, arguments: Mapping[str, Any]) -> Any:
        call = LaunchCall(
            agent_id=agent.agent_id,
            command=agent.command,
            args=tuple(agent.args),
            env=dict(agent.env),
            url=agent.url,
            transport=agent.transport,
            headers=dict(agent.headers),
            tool_name=tool_name,
            arguments=dict(arguments),
        )
        calls.append(call)
        return {
            "agent_id": agent.agent_id,
            "tool": tool_name,
            "arguments": dict(arguments),
            "ok": True,
        }

    return calls, launcher
