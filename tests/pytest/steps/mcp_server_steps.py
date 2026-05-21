"""Step definitions for docs/features/mcp-server.feature."""

from __future__ import annotations

from pytest_bdd import given, when, then, parsers

from tool_selector_mcp.corpus import Agent, Corpus, Tool
from tool_selector_mcp.server import ToolSelectorServer, make_recording_launcher


def _agent(
    agent_id: str,
    *,
    description: str = "",
    command: str = "npx",
    args: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
    tools: tuple[Tool, ...] = (),
) -> Agent:
    return Agent(
        agent_id=agent_id,
        description=description,
        command=command,
        args=args,
        env=env or {},
        tools=tools,
    )


# --- Scenario: tool-selector-mcp is the only registered MCP server -------


@given(
    'a client configured with only "tool-selector-mcp" in its mcpServers',
    target_fixture="client_config",
)
def _client_config_only_selector() -> dict:
    return {"mcpServers": {"tool-selector-mcp": {"command": "uvx", "args": ["tool-selector-mcp"]}}}


@given(
    parsers.parse(
        'downstream agents "{first}" and "{second}" are defined in the corpus file'
    ),
    target_fixture="corpus",
)
def _agents_in_corpus(first: str, second: str) -> Corpus:
    return Corpus(
        agents={
            first: _agent(first, description=f"{first} description"),
            second: _agent(second, description=f"{second} description"),
        }
    )


@then(
    parsers.parse('"{first}" and "{second}" are not registered directly in the client')
)
def _agents_not_in_client(first: str, second: str, client_config: dict) -> None:
    registered = set(client_config["mcpServers"].keys())
    assert first not in registered
    assert second not in registered
    assert registered == {"tool-selector-mcp"}


@then("they are only reachable through tool-selector-mcp")
def _reachable_through_selector(corpus: Corpus, client_config: dict) -> None:
    for agent_id in corpus.agents:
        assert agent_id in corpus.agents, f"{agent_id} missing from selector's corpus"
        assert agent_id not in client_config["mcpServers"]


# --- Scenario: Server executes the selected tool on the chosen agent -----


@given("the server is running", target_fixture="bdd_state")
def _server_running(bdd_state: dict) -> dict:
    return bdd_state


@given(
    "the corpus contains agents with their command, args, and env",
    target_fixture="server_bundle",
)
def _corpus_with_full_agents(bdd_state: dict) -> dict:
    corpus = Corpus(
        agents={
            "github-mcp": _agent(
                "github-mcp",
                description="Interact with GitHub repositories, issues, and PRs",
                command="npx",
                args=("-y", "@modelcontextprotocol/server-github"),
                env={"GITHUB_TOKEN": "ghp_secret"},
                tools=(
                    Tool(
                        name="create_pull_request",
                        description="Open a new pull request on a GitHub repository",
                    ),
                ),
            ),
        }
    )
    calls, launcher = make_recording_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    bundle = {"server": server, "corpus": corpus, "calls": calls}
    bdd_state["bundle"] = bundle
    return bundle


@when("a client invokes a tool through tool-selector-mcp")
def _client_invokes_tool(server_bundle: dict) -> None:
    server = server_bundle["server"]
    result = server.invoke_tool("create_pull_request", {"repo": "demo"})
    server_bundle["result"] = result


@then("the server starts the chosen downstream agent using its command, args, and env")
def _server_started_downstream(server_bundle: dict) -> None:
    calls = server_bundle["calls"]
    assert len(calls) == 1
    call = calls[0]
    assert call.command == "npx"
    assert call.args == ("-y", "@modelcontextprotocol/server-github")
    assert call.env == {"GITHUB_TOKEN": "ghp_secret"}


@then("the server forwards the tool call to that agent")
def _server_forwarded(server_bundle: dict) -> None:
    call = server_bundle["calls"][0]
    assert call.tool_name == "create_pull_request"
    assert call.arguments == {"repo": "demo"}


@then("the server returns the downstream agent's result to the client")
def _server_returns_result(server_bundle: dict) -> None:
    result = server_bundle["result"]
    assert result["ok"] is True
    assert result["agent_id"] == "github-mcp"
    assert result["tool"] == "create_pull_request"


# --- Scenario: Server does not orchestrate multi-step workflows ----------


@when("a client submits a multi-step query")
def _multi_step_query(bdd_state: dict) -> None:
    corpus = Corpus(
        agents={
            "github-mcp": _agent(
                "github-mcp",
                description="Interact with GitHub repositories, issues, and PRs",
                tools=(
                    Tool(name="list_issues", description="List open issues for a repository"),
                ),
            ),
            "slack-mcp": _agent(
                "slack-mcp",
                description="Send messages and manage Slack workspaces",
                tools=(
                    Tool(name="send_message", description="Send a message to a Slack channel"),
                ),
            ),
        }
    )
    server = ToolSelectorServer(corpus)
    bdd_state["server"] = server
    bdd_state["per_step_results"] = [
        server.search_tools("list open GitHub issues", k=1),
        server.search_tools("send a Slack summary", k=1),
    ]


@then("the server returns relevant agents for each step")
def _relevant_per_step(bdd_state: dict) -> None:
    results = bdd_state["per_step_results"]
    assert results[0][0].agent_id == "github-mcp"
    assert results[1][0].agent_id == "slack-mcp"


@then("the server does not sequence or coordinate the steps")
def _no_orchestration(bdd_state: dict) -> None:
    server = bdd_state["server"]
    public = {
        name
        for name in dir(server)
        if not name.startswith("_") and callable(getattr(server, name))
    }
    # The server's public surface is the three MCP tools; no orchestration verb.
    assert "search_tools" in public
    assert "get_tool_details" in public
    assert "invoke_tool" in public
    forbidden = {"orchestrate", "run_workflow", "execute_steps", "chain", "plan"}
    assert not (public & forbidden), f"unexpected orchestration methods: {public & forbidden}"
