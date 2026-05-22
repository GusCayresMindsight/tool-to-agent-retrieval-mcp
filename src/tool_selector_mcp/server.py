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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .corpus import Agent, Corpus, Tool
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
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str]
    tool_name: str
    arguments: Mapping[str, Any]


Launcher = Callable[[Agent, str, Mapping[str, Any]], Any]


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
    ) -> None:
        self.corpus = corpus
        self._launcher = launcher
        self.rewrite_queries = rewrite_queries

    # --- exposed MCP tools -------------------------------------------------

    def search_tools(self, query: str, k: int = 1) -> list[SearchHit]:
        results = search(
            self.corpus,
            query,
            k=k,
            rewrite=self.rewrite_queries,
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
