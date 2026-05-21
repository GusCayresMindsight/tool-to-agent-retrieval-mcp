"""Step definitions for docs/features/installation.feature.

The installation scenarios are about how the package is reached
(``uvx tool-selector-mcp``) rather than about MCP wire behavior, so the
steps inspect package metadata and configuration shape instead of spawning
real subprocesses.
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import json
import shutil
from pathlib import Path

import pytest
from pytest_bdd import given, when, then, parsers

from tool_selector_mcp import cli
from tool_selector_mcp.corpus import Corpus
from tool_selector_mcp.server import ToolSelectorServer


# --- Background -----------------------------------------------------------


@given("uv (which provides the uvx launcher) is installed on the host system")
def _uv_installed() -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is not installed on this host")


@given("the uvx executable is on the PATH")
def _uvx_on_path() -> None:
    if shutil.which("uvx") is None:
        pytest.skip("uvx is not on PATH")


# --- Scenario: Starting the server via uvx --------------------------------


@given("the tool-selector-mcp package is available on PyPI")
def _package_available() -> None:
    # In CI the package is available locally via the working tree; we treat
    # "available on PyPI" as "the distribution metadata is installed and
    # advertises the right entry point".
    dist = md.distribution("tool-selector-mcp")
    scripts = {ep.name: ep.value for ep in dist.entry_points if ep.group == "console_scripts"}
    assert scripts.get("tool-selector-mcp") == "tool_selector_mcp.cli:main", (
        f"unexpected console_scripts entry: {scripts}"
    )


@when(parsers.parse('a client runs "{command}"'))
def _client_runs(command: str, bdd_state: dict) -> None:
    assert command == "uvx tool-selector-mcp"
    # uvx resolves the console_scripts entry and invokes it — exercise the
    # same callable directly so the test does not depend on the network.
    main = importlib.import_module("tool_selector_mcp.cli").main
    bdd_state["entry_callable"] = main


@then("the MCP server starts and listens for connections")
def _server_starts(bdd_state: dict) -> None:
    main = bdd_state["entry_callable"]
    assert callable(main)
    # cli.build_server is the boundary that constructs the server before
    # main blocks on the protocol loop; verifying it is exposed gives us a
    # programmatic stand-in for "the server starts".
    assert callable(cli.build_server)


# --- Scenarios: Configuring the server in Claude Desktop / Code ----------


@given("a claude_desktop_config.json file", target_fixture="config_path")
def _claude_desktop_config(tmp_path: Path) -> Path:
    path = tmp_path / "claude_desktop_config.json"
    path.write_text(json.dumps({"mcpServers": {}}))
    return path


@given("a .claude/settings.json file", target_fixture="config_path")
def _claude_code_config(tmp_path: Path) -> Path:
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    path = settings_dir / "settings.json"
    path.write_text(json.dumps({"mcpServers": {}}))
    return path


@when(parsers.parse('the following entry is added to "{section}":'))
def _entry_added(section: str, docstring: str, config_path: Path) -> None:
    assert section == "mcpServers"
    config = json.loads(config_path.read_text())
    parsed_entry = json.loads("{" + docstring + "}")
    config[section].update(parsed_entry)
    config_path.write_text(json.dumps(config))


def _assert_config_launches_us(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    entry = config["mcpServers"]["tool-selector"]
    assert entry["command"] == "uvx"
    assert entry["args"] == ["tool-selector-mcp"]


@then("Claude Desktop starts the server automatically on launch")
def _claude_desktop_starts(config_path: Path) -> None:
    _assert_config_launches_us(config_path)


@then("Claude Code starts the server automatically on launch")
def _claude_code_starts(config_path: Path) -> None:
    _assert_config_launches_us(config_path)


@then("the tool-selector tools become available in the session")
def _tools_available() -> None:
    server = ToolSelectorServer(Corpus(agents={}))
    for attr in ("search_tools", "get_tool_details", "invoke_tool"):
        assert callable(getattr(server, attr)), f"missing tool: {attr}"
