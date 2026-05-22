"""Step definitions for docs/features/subprocess-launcher.feature."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_bdd import given, parsers, then, when

from tool_selector_mcp.corpus import Agent, Tool
from tool_selector_mcp.server import make_subprocess_launcher


def _state(bdd_state: dict) -> dict:
    return bdd_state.setdefault("subprocess_launcher", {})


def _build_mock_client(return_value: object = None) -> dict:
    """Build a fully mocked MCP stdio client + session."""
    mock_read = MagicMock()
    mock_write = MagicMock()

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=return_value)

    # stdio_client(params) → async context manager that yields (read, write)
    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
    mock_stdio_client = MagicMock(return_value=mock_stdio_cm)

    # ClientSession(read, write) → async context manager that yields session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)
    MockClientSession = MagicMock(return_value=mock_session_cm)

    return {
        "mock_stdio_client": mock_stdio_client,
        "MockClientSession": MockClientSession,
        "mock_session": mock_session,
    }


# --- Given steps ---------------------------------------------------------


@given(parsers.parse('a subprocess launcher agent with command "{command}" and args {args_json}'))
def _agent_for_launcher(command: str, args_json: str, bdd_state: dict) -> None:
    args = json.loads(args_json)
    _state(bdd_state)["agent"] = Agent(
        agent_id="test-agent",
        description="test agent",
        command=command,
        args=tuple(args),
        env={},
        tools=(Tool(name="create_issue", description="Create an issue", input_schema={}),),
    )


@given("the MCP client is mocked")
def _mock_client_default(bdd_state: dict) -> None:
    _state(bdd_state).update(_build_mock_client(return_value={"content": "ok"}))


@given(parsers.parse("the MCP client is mocked to return {return_value_json}"))
def _mock_client_with_return(return_value_json: str, bdd_state: dict) -> None:
    return_value = json.loads(return_value_json)
    _state(bdd_state).update(_build_mock_client(return_value=return_value))


# --- When steps ----------------------------------------------------------


@when(
    parsers.parse(
        'the subprocess launcher is called with tool "{tool_name}" and arguments {args_json}'
    )
)
def _call_subprocess_launcher(tool_name: str, args_json: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    agent: Agent = state["agent"]
    args = json.loads(args_json)

    with (
        patch("mcp.client.stdio.stdio_client", state["mock_stdio_client"]),
        patch("mcp.ClientSession", state["MockClientSession"]),
    ):
        launcher = make_subprocess_launcher()
        try:
            state["result"] = asyncio.run(launcher(agent, tool_name, args))
            state["error"] = None
        except Exception as exc:
            state["result"] = None
            state["error"] = exc


# --- Then steps ----------------------------------------------------------


@then(parsers.parse('stdio_client received command "{command}" and args {args_json}'))
def _stdio_client_received_params(command: str, args_json: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    expected_args = json.loads(args_json)
    mock_stdio_client = state["mock_stdio_client"]
    assert mock_stdio_client.called, "stdio_client was never called"
    params = mock_stdio_client.call_args[0][0]
    assert params.command == command
    assert list(params.args) == expected_args


@then(parsers.parse('session.call_tool was called with "{tool_name}" and {args_json}'))
def _session_call_tool_called(tool_name: str, args_json: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    expected_args = json.loads(args_json)
    mock_session = state["mock_session"]
    mock_session.call_tool.assert_called_once_with(tool_name, expected_args)


@then(parsers.parse("the subprocess launcher returns {expected_json}"))
def _launcher_returns(expected_json: str, bdd_state: dict) -> None:
    expected = json.loads(expected_json)
    result = _state(bdd_state)["result"]
    assert result == expected, f"expected {expected!r}, got {result!r}"
