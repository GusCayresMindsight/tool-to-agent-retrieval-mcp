"""Corpus loading for tool-selector-mcp.

The corpus file extends the .mcp.json layout used by Claude clients with
agent-level ``description`` fields and per-agent ``tools`` lists. Tool entries
mirror the MCP tool schema so they can be returned via ``get_tool_details``.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CORPUS_FILENAME = ".mcp-corpus.json"
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class CorpusError(Exception):
    """Base class for corpus-loading failures."""


class CorpusFileNotFoundError(CorpusError):
    def __init__(self, path: Path):
        super().__init__(f"corpus file not found: {path}")
        self.path = path


class CorpusEnvVarUnresolvedError(CorpusError):
    def __init__(self, var_name: str):
        super().__init__(f"unresolved environment variable: {var_name}")
        self.var_name = var_name


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Agent:
    agent_id: str
    description: str
    command: str | None = None
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    url: str | None = None
    transport: str = "stdio"
    headers: Mapping[str, str] = field(default_factory=dict)
    tools: tuple[Tool, ...] = ()


@dataclass(frozen=True)
class Corpus:
    agents: Mapping[str, Agent]

    def get_agent(self, agent_id: str) -> Agent | None:
        return self.agents.get(agent_id)

    def find_tool(self, tool_name: str) -> tuple[Agent, Tool] | None:
        for agent in self.agents.values():
            for tool in agent.tools:
                if tool.name == tool_name:
                    return (agent, tool)
        return None


def resolve_corpus_path(
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    """Return the corpus path honoring MCP_CORPUS_PATH, else the cwd default."""
    env = os.environ if env is None else env
    cwd = cwd or Path.cwd()
    custom = env.get("MCP_CORPUS_PATH")
    if custom:
        return Path(custom)
    return cwd / DEFAULT_CORPUS_FILENAME


def _resolve_env_block(
    env_block: Mapping[str, str],
    host_env: Mapping[str, str],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, value in env_block.items():

        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in host_env:
                raise CorpusEnvVarUnresolvedError(name)
            return host_env[name]

        resolved[key] = ENV_VAR_PATTERN.sub(repl, value)
    return resolved


def load_corpus(
    path: Path,
    host_env: Mapping[str, str] | None = None,
) -> Corpus:
    """Load and validate a corpus file at ``path``.

    Raises ``CorpusFileNotFoundError`` if the file is missing and
    ``CorpusEnvVarUnresolvedError`` if any ``${VAR}`` reference cannot be
    resolved from ``host_env`` (defaults to ``os.environ``).
    """
    if host_env is None:
        host_env = dict(os.environ)
    if not path.exists():
        raise CorpusFileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_servers = data.get("mcpServers", {})
    agents: dict[str, Agent] = {}
    for agent_id, spec in raw_servers.items():
        tools = tuple(
            Tool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in spec.get("tools", [])
        )
        env_block = _resolve_env_block(spec.get("env", {}), host_env)
        headers_block = _resolve_env_block(spec.get("headers", {}), host_env)
        agents[agent_id] = Agent(
            agent_id=agent_id,
            description=spec.get("description", ""),
            command=spec.get("command"),
            args=tuple(spec.get("args", [])),
            env=env_block,
            url=spec.get("url"),
            transport=spec.get("transport", "stdio" if spec.get("command") else "sse"),
            headers=headers_block,
            tools=tools,
        )
    return Corpus(agents=agents)
