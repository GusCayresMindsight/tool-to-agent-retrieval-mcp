"""Step definitions for docs/features/corpus-configuration.feature."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, when, then, parsers

from tool_selector_mcp.corpus import (
    Corpus,
    CorpusEnvVarUnresolvedError,
    CorpusFileNotFoundError,
    load_corpus,
    resolve_corpus_path,
)
from tool_selector_mcp.server import ToolSelectorServer, make_recording_launcher


# --- Helpers -------------------------------------------------------------


def _state(bdd_state: dict) -> dict:
    return bdd_state.setdefault("corpus_cfg", {})


def _stash_path(bdd_state: dict, label: str, path: Path) -> None:
    _state(bdd_state).setdefault("paths", {})[label] = path


# --- Filesystem setup steps ----------------------------------------------


@given(
    parsers.parse('a file ".mcp-corpus.json" exists in the current working directory'),
)
def _default_corpus_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bdd_state: dict) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".mcp-corpus.json"
    path.write_text(json.dumps({"mcpServers": {"default-agent": {"command": "echo"}}}))
    _stash_path(bdd_state, "default", path)


@given(parsers.parse('a corpus file exists at "{path}"'))
def _custom_corpus_exists(path: str, tmp_path: Path, bdd_state: dict) -> None:
    target = tmp_path / "custom_corpus.json"
    target.write_text(json.dumps({"mcpServers": {"custom-agent": {"command": "echo"}}}))
    _state(bdd_state).setdefault("path_aliases", {})[path] = target
    _stash_path(bdd_state, path, target)


@given(parsers.parse('the environment variable MCP_CORPUS_PATH is set to "{path}"'))
def _set_corpus_env(path: str, monkeypatch: pytest.MonkeyPatch, bdd_state: dict) -> None:
    aliased = _state(bdd_state).get("path_aliases", {}).get(path)
    if aliased is not None:
        monkeypatch.setenv("MCP_CORPUS_PATH", str(aliased))
    else:
        monkeypatch.setenv("MCP_CORPUS_PATH", path)


@given("no corpus file exists at the configured path")
def _no_corpus_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # default path will not exist


@given(parsers.parse('a ".mcp-corpus.json" file with the following content:'))
def _corpus_file_with_content(
    docstring: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bdd_state: dict,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".mcp-corpus.json"
    path.write_text(docstring)
    _stash_path(bdd_state, "default", path)


@given(parsers.parse('a corpus entry with env {{ "{var}": "${{{ref}}}" }}'))
def _corpus_entry_unresolved_env(
    var: str,
    ref: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bdd_state: dict,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".mcp-corpus.json"
    body = {
        "mcpServers": {
            "needy-agent": {
                "command": "echo",
                "env": {var: "${" + ref + "}"},
                "description": "",
                "tools": [],
            }
        }
    }
    path.write_text(json.dumps(body))
    _stash_path(bdd_state, "default", path)
    _state(bdd_state)["expected_unresolved"] = ref


@given(parsers.parse('the host environment variable {var} is set to "{value}"'))
def _set_host_env(var: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(var, value)


@given(parsers.parse("the host environment variable {var} is not set"))
def _unset_host_env(var: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(var, raising=False)


# --- Inline scenario for "Server executes the selected agent's tool" -----


@given(
    parsers.parse(
        'the corpus contains "{agent_id}" with command "{command}", '
        'args [{args}], and env {env_var}'
    )
)
def _corpus_with_executable_agent(
    agent_id: str,
    command: str,
    args: str,
    env_var: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bdd_state: dict,
) -> None:
    monkeypatch.setenv(env_var, "ghp_secret")
    arg_list = [a.strip().strip('"') for a in args.split(",")]
    body = {
        "mcpServers": {
            agent_id: {
                "command": command,
                "args": arg_list,
                "env": {env_var: "${" + env_var + "}"},
                "description": "",
                "tools": [
                    {
                        "name": "create_pull_request",
                        "description": "Open a new pull request on a GitHub repository",
                    }
                ],
            }
        }
    }
    path = tmp_path / ".mcp-corpus.json"
    path.write_text(json.dumps(body))
    monkeypatch.chdir(tmp_path)
    _stash_path(bdd_state, "default", path)
    _state(bdd_state)["expected"] = {
        "agent_id": agent_id,
        "command": command,
        "args": tuple(arg_list),
        "env_var": env_var,
    }


# --- "When the server starts" -------------------------------------------


@when(parsers.parse('the server starts via "{command}"'))
def _server_starts_via(command: str, bdd_state: dict) -> None:
    assert command == "uvx tool-selector-mcp"
    _load_corpus_into_state(bdd_state)


@when("the server starts")
def _server_starts(bdd_state: dict) -> None:
    _load_corpus_into_state(bdd_state)


@when(parsers.parse('the server launches "{agent_id}" to handle a tool call'))
def _server_launches_agent(agent_id: str, bdd_state: dict) -> None:
    _load_corpus_into_state(bdd_state)
    corpus = _state(bdd_state)["corpus"]
    calls, launcher = make_recording_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    agent = corpus.get_agent(agent_id)
    assert agent is not None, f"corpus missing agent {agent_id}"
    if agent.tools:
        tool_name = agent.tools[0].name
    else:
        tool_name = "ping"
        # Inject a placeholder so invoke_tool can resolve; tests using this
        # branch only need to observe the launcher input.
        # (No tools = empty list scenario currently always has at least one
        # tool in the feature file's body, so this fallback is defensive.)
    if any(t.name == tool_name for t in agent.tools):
        server.invoke_tool(tool_name, {}, server=agent_id)
    else:
        # Bypass the corpus lookup by calling the launcher directly.
        from tool_selector_mcp.server import LaunchCall  # noqa: F401
        launcher(agent, tool_name, {})
    _state(bdd_state)["launcher_calls"] = calls


@when(parsers.parse('a client invokes a tool that resolves to "{agent_id}"'))
def _client_invokes_via_selector(agent_id: str, bdd_state: dict) -> None:
    _load_corpus_into_state(bdd_state)
    corpus = _state(bdd_state)["corpus"]
    calls, launcher = make_recording_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    agent = corpus.get_agent(agent_id)
    assert agent is not None
    tool_name = agent.tools[0].name
    result = server.invoke_tool(tool_name, {}, server=agent_id)
    _state(bdd_state)["launcher_calls"] = calls
    _state(bdd_state)["result"] = result


def _load_corpus_into_state(bdd_state: dict) -> None:
    state = _state(bdd_state)
    path = resolve_corpus_path()
    state["resolved_path"] = path
    try:
        state["corpus"] = load_corpus(path)
        state["error"] = None
    except (CorpusFileNotFoundError, CorpusEnvVarUnresolvedError) as exc:
        state["corpus"] = None
        state["error"] = exc


# --- Outcome assertions --------------------------------------------------


@then(parsers.parse('the catalog is populated from "{path}"'))
def _catalog_populated_from(path: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    assert state["corpus"] is not None, "corpus failed to load"
    resolved = state["resolved_path"]
    aliased = state.get("path_aliases", {}).get(path)
    if aliased is not None:
        assert Path(resolved) == aliased
    else:
        # Default path: just check the filename matches.
        assert Path(resolved).name == Path(path).name


@then(parsers.parse('"{path}" is not read'))
def _default_path_not_read(path: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    resolved = state["resolved_path"]
    assert Path(resolved).name != Path(path).name or _state(bdd_state).get("path_aliases", {}).get(path) is not None
    # When MCP_CORPUS_PATH is set, resolve_corpus_path returns the env value
    # and the default file is never opened. Verify by checking the resolved
    # path is the aliased custom path, not the default.
    custom_alias = next(iter(_state(bdd_state).get("path_aliases", {}).values()), None)
    if custom_alias is not None:
        assert Path(resolved) == custom_alias


@then("the server exits with an error indicating the corpus file was not found")
def _server_exit_corpus_missing(bdd_state: dict) -> None:
    err = _state(bdd_state)["error"]
    assert isinstance(err, CorpusFileNotFoundError)


@then(parsers.parse('the catalog contains the agent "{agent_id}" with {count:d} tool'))
@then(parsers.parse('the catalog contains the agent "{agent_id}" with {count:d} tools'))
def _catalog_contains_agent(agent_id: str, count: int, bdd_state: dict) -> None:
    corpus: Corpus = _state(bdd_state)["corpus"]
    agent = corpus.get_agent(agent_id)
    assert agent is not None, f"agent {agent_id} not in catalog"
    assert len(agent.tools) == count, (
        f"expected {count} tools on {agent_id}, found {len(agent.tools)}"
    )


@then(parsers.parse('the agent is started with {var}="{value}"'))
def _agent_started_with_env(var: str, value: str, bdd_state: dict) -> None:
    calls = _state(bdd_state)["launcher_calls"]
    assert len(calls) == 1
    assert calls[0].env.get(var) == value


@then(parsers.parse('the server exits with an error indicating {var} is unresolved'))
def _server_exit_env_unresolved(var: str, bdd_state: dict) -> None:
    err = _state(bdd_state)["error"]
    assert isinstance(err, CorpusEnvVarUnresolvedError)
    assert err.var_name == var


@then(parsers.parse('the server launches "{agent_id}" with its command, args, and resolved env'))
def _server_launches_with_full_config(agent_id: str, bdd_state: dict) -> None:
    calls = _state(bdd_state)["launcher_calls"]
    expected = _state(bdd_state)["expected"]
    assert len(calls) == 1
    call = calls[0]
    assert call.agent_id == agent_id == expected["agent_id"]
    assert call.command == expected["command"]
    assert call.args == expected["args"]
    assert call.env[expected["env_var"]] == "ghp_secret"


@then("the server returns the result of the tool call to the client")
def _server_returns_tool_result(bdd_state: dict) -> None:
    result = _state(bdd_state)["result"]
    assert result["ok"] is True
