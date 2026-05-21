"""Step definitions for docs/features/server-tools.feature."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pytest
from pytest_bdd import given, when, then, parsers

from tool_selector_mcp.corpus import Agent, Corpus, Tool
from tool_selector_mcp.server import (
    ToolSelectorServer,
    UnknownToolError,
    make_recording_launcher,
)


# --- Helpers -------------------------------------------------------------


def _agent(
    agent_id: str,
    description: str,
    *,
    tools: tuple[Tool, ...] = (),
) -> Agent:
    return Agent(
        agent_id=agent_id,
        description=description,
        command="npx",
        args=(),
        env={},
        tools=tools,
    )


def _default_tools() -> dict[str, tuple[Tool, ...]]:
    return {
        "github-mcp": (
            Tool(
                name="create_pull_request",
                description="Open a new pull request on a GitHub repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                    },
                    "required": ["repo", "title"],
                },
            ),
            Tool(
                name="list_issues",
                description="List open issues for a repository",
                input_schema={
                    "type": "object",
                    "properties": {"repo": {"type": "string"}},
                },
            ),
        ),
        "postgres-mcp": (
            Tool(
                name="run_query",
                description="Execute a SQL query on a PostgreSQL database",
                input_schema={
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                },
            ),
        ),
        "slack-mcp": (
            Tool(
                name="send_message",
                description="Send a message to a Slack channel",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "text": {"type": "string"},
                    },
                },
            ),
        ),
    }


_DEFAULT_AGENT_DESCRIPTIONS = {
    "github-mcp": "Interact with GitHub repositories, issues, and PRs",
    "postgres-mcp": "Execute queries and manage PostgreSQL databases",
    "slack-mcp": "Send messages and manage Slack workspaces",
}


def _state(bdd_state: dict) -> dict:
    return bdd_state.setdefault("server_tools", {})


# --- Given steps ---------------------------------------------------------


@given(
    parsers.re(
        r'the server is running with a corpus containing '
        r'"(?P<a>[^"]+)", "(?P<b>[^"]+)", and "(?P<c>[^"]+)"'
    )
)
def _running_with_corpus(a: str, b: str, c: str, bdd_state: dict) -> None:
    tools_by_agent = _default_tools()
    agents = {
        aid: _agent(
            aid,
            _DEFAULT_AGENT_DESCRIPTIONS.get(aid, ""),
            tools=tools_by_agent.get(aid, ()),
        )
        for aid in (a, b, c)
    }
    corpus = Corpus(agents=agents)
    calls, launcher = make_recording_launcher()
    _state(bdd_state)["server"] = ToolSelectorServer(corpus, launcher=launcher)
    _state(bdd_state)["calls"] = calls
    _state(bdd_state)["corpus"] = corpus


@given(
    parsers.parse(
        'the corpus contains "{agent_id}" with tool "{tool_name}" having a large input schema'
    )
)
def _corpus_with_large_schema(agent_id: str, tool_name: str, bdd_state: dict) -> None:
    big_schema = {
        "type": "object",
        "properties": {f"field_{i}": {"type": "string"} for i in range(50)},
        "required": [f"field_{i}" for i in range(10)],
    }
    tools = (Tool(name=tool_name, description="Open a new pull request on a GitHub repository", input_schema=big_schema),)
    corpus = Corpus(
        agents={agent_id: _agent(agent_id, _DEFAULT_AGENT_DESCRIPTIONS.get(agent_id, ""), tools=tools)}
    )
    calls, launcher = make_recording_launcher()
    _state(bdd_state)["server"] = ToolSelectorServer(corpus, launcher=launcher)
    _state(bdd_state)["calls"] = calls
    _state(bdd_state)["corpus"] = corpus
    _state(bdd_state)["large_schema"] = big_schema


@given(
    parsers.parse(
        'the corpus contains "{agent_id}" with tools "{first}" and "{second}"'
    )
)
def _corpus_with_two_tools(
    agent_id: str, first: str, second: str, bdd_state: dict
) -> None:
    by_name = {t.name: t for t in _default_tools()[agent_id]}
    tools = (by_name[first], by_name[second])
    corpus = Corpus(
        agents={agent_id: _agent(agent_id, _DEFAULT_AGENT_DESCRIPTIONS[agent_id], tools=tools)}
    )
    _state(bdd_state)["server"] = ToolSelectorServer(corpus)
    _state(bdd_state)["corpus"] = corpus


@given(parsers.parse('the corpus does not contain a tool named "{tool_name}"'))
def _corpus_missing_tool(tool_name: str, bdd_state: dict) -> None:
    # Build a corpus that explicitly lacks ``tool_name``.
    corpus = Corpus(
        agents={
            "github-mcp": _agent(
                "github-mcp",
                _DEFAULT_AGENT_DESCRIPTIONS["github-mcp"],
                tools=_default_tools()["github-mcp"],
            )
        }
    )
    assert corpus.find_tool(tool_name) is None
    calls, launcher = make_recording_launcher()
    _state(bdd_state)["server"] = ToolSelectorServer(corpus, launcher=launcher)
    _state(bdd_state)["corpus"] = corpus


@given(parsers.parse('the corpus contains agent "{agent_id}" with tool "{tool_name}"'))
def _corpus_with_agent_and_tool(agent_id: str, tool_name: str, bdd_state: dict) -> None:
    tool = next(t for t in _default_tools()[agent_id] if t.name == tool_name)
    corpus = Corpus(
        agents={agent_id: _agent(agent_id, _DEFAULT_AGENT_DESCRIPTIONS[agent_id], tools=(tool,))}
    )
    calls, launcher = make_recording_launcher()
    _state(bdd_state)["server"] = ToolSelectorServer(corpus, launcher=launcher)
    _state(bdd_state)["calls"] = calls
    _state(bdd_state)["corpus"] = corpus


@given(parsers.parse('the corpus contains tool "{tool_name}" owned by "{agent_id}"'))
def _corpus_tool_owned_by(tool_name: str, agent_id: str, bdd_state: dict) -> None:
    tool = next(t for t in _default_tools()[agent_id] if t.name == tool_name)
    corpus = Corpus(
        agents={agent_id: _agent(agent_id, _DEFAULT_AGENT_DESCRIPTIONS[agent_id], tools=(tool,))}
    )
    calls, launcher = make_recording_launcher()
    _state(bdd_state)["server"] = ToolSelectorServer(corpus, launcher=launcher)
    _state(bdd_state)["calls"] = calls
    _state(bdd_state)["corpus"] = corpus


# --- When steps ----------------------------------------------------------


@when(
    parsers.parse(
        'search_tools is called with query "{query}" and K={k:d}'
    )
)
def _call_search_with_k(query: str, k: int, bdd_state: dict) -> None:
    server: ToolSelectorServer = _state(bdd_state)["server"]
    _state(bdd_state)["search_result"] = server.search_tools(query, k=k)


@when(
    parsers.parse(
        'search_tools is called with query "{query}" without specifying K'
    )
)
def _call_search_default(query: str, bdd_state: dict) -> None:
    server: ToolSelectorServer = _state(bdd_state)["server"]
    _state(bdd_state)["search_result"] = server.search_tools(query)


@when(
    parsers.re(
        r'get_tool_details is called with \[(?P<ids>.+)\]$'
    )
)
def _call_get_tool_details(ids: str, bdd_state: dict) -> None:
    tool_ids = [s.strip().strip('"') for s in ids.split(",")]
    server: ToolSelectorServer = _state(bdd_state)["server"]
    try:
        _state(bdd_state)["details_result"] = server.get_tool_details(tool_ids)
        _state(bdd_state)["details_error"] = None
    except UnknownToolError as exc:
        _state(bdd_state)["details_result"] = None
        _state(bdd_state)["details_error"] = exc


@when(
    parsers.parse(
        'invoke_tool is called with server "{server_id}", tool "{tool_name}", '
        'and arguments {arguments}'
    )
)
def _invoke_with_server(server_id: str, tool_name: str, arguments: str, bdd_state: dict) -> None:
    server: ToolSelectorServer = _state(bdd_state)["server"]
    args = json.loads(arguments)
    try:
        _state(bdd_state)["invoke_result"] = server.invoke_tool(
            tool_name, args, server=server_id
        )
        _state(bdd_state)["invoke_error"] = None
    except UnknownToolError as exc:
        _state(bdd_state)["invoke_result"] = None
        _state(bdd_state)["invoke_error"] = exc


@when(
    parsers.parse(
        'invoke_tool is called with tool "{tool_name}" and arguments {arguments}'
    )
)
def _invoke_with_tool_only(tool_name: str, arguments: str, bdd_state: dict) -> None:
    server: ToolSelectorServer = _state(bdd_state)["server"]
    args = json.loads(arguments)
    try:
        _state(bdd_state)["invoke_result"] = server.invoke_tool(tool_name, args)
        _state(bdd_state)["invoke_error"] = None
    except UnknownToolError as exc:
        _state(bdd_state)["invoke_result"] = None
        _state(bdd_state)["invoke_error"] = exc


# --- Then steps ----------------------------------------------------------


@then(parsers.parse("the result contains {count:d} agent"))
@then(parsers.parse("the result contains {count:d} agents"))
def _result_contains(count: int, bdd_state: dict) -> None:
    assert len(_state(bdd_state)["search_result"]) == count


@then(parsers.parse('"{agent_id}" is the top result'))
def _top_result(agent_id: str, bdd_state: dict) -> None:
    hits = _state(bdd_state)["search_result"]
    assert hits, "search returned no hits"
    assert hits[0].agent_id == agent_id


@then(parsers.parse("the result contains at most {count:d} agents"))
def _result_at_most(count: int, bdd_state: dict) -> None:
    assert len(_state(bdd_state)["search_result"]) <= count


@then(parsers.parse("the result contains exactly {count:d} agent"))
@then(parsers.parse("the result contains exactly {count:d} agents"))
def _result_exactly(count: int, bdd_state: dict) -> None:
    assert len(_state(bdd_state)["search_result"]) == count


@then("each result includes the agent id, tool name, and a short description")
def _result_has_metadata(bdd_state: dict) -> None:
    hits = _state(bdd_state)["search_result"]
    assert hits
    for hit in hits:
        assert hit.agent_id
        # Either matched via tool (tool_name set) or via agent (None is OK)
        assert hit.description != ""


@then("the result does not include the tool's full input schema")
def _result_no_schema(bdd_state: dict) -> None:
    hits = _state(bdd_state)["search_result"]
    big = _state(bdd_state).get("large_schema")
    for hit in hits:
        as_dict = asdict(hit)
        assert "input_schema" not in as_dict, (
            f"unexpected input_schema in search hit: {as_dict}"
        )
        if big is not None:
            for value in as_dict.values():
                if isinstance(value, dict):
                    assert value != big


@then("the result contains the full input schema for each requested tool")
def _details_have_schemas(bdd_state: dict) -> None:
    details = _state(bdd_state)["details_result"]
    assert details
    for detail in details:
        assert detail.input_schema, f"missing schema for {detail.tool_name}"
        assert detail.input_schema.get("type") == "object"


@then("the server returns an error indicating the tool was not found")
def _error_tool_not_found(bdd_state: dict) -> None:
    err = _state(bdd_state).get("details_error") or _state(bdd_state).get("invoke_error")
    assert err is not None
    assert isinstance(err, UnknownToolError)


@then(parsers.parse('the server starts "{agent_id}" using its command, args, and resolved env'))
def _invoke_started_agent(agent_id: str, bdd_state: dict) -> None:
    calls = _state(bdd_state)["calls"]
    assert len(calls) == 1
    assert calls[0].agent_id == agent_id
    assert calls[0].command == "npx"


@then(parsers.parse('the server forwards the call to "{tool_name}" on that agent'))
def _invoke_forwarded(tool_name: str, bdd_state: dict) -> None:
    call = _state(bdd_state)["calls"][0]
    assert call.tool_name == tool_name
    assert call.arguments == {"repo": "my-repo", "title": "Fix bug"}


@then("the server returns the agent's response to the client")
def _invoke_returned_result(bdd_state: dict) -> None:
    result = _state(bdd_state)["invoke_result"]
    assert result["ok"] is True


@then(parsers.parse('the server identifies "{agent_id}" as the target agent'))
def _invoke_identifies_agent(agent_id: str, bdd_state: dict) -> None:
    calls = _state(bdd_state)["calls"]
    assert len(calls) == 1
    assert calls[0].agent_id == agent_id


@then("the server forwards the call and returns the result")
def _invoke_forward_and_return(bdd_state: dict) -> None:
    call = _state(bdd_state)["calls"][0]
    assert call.arguments == {"repo": "my-repo", "title": "Fix bug"}
    result = _state(bdd_state)["invoke_result"]
    assert result["ok"] is True
