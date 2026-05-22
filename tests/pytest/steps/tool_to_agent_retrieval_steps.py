"""Step definitions for docs/features/tool-retrieval.feature."""

from __future__ import annotations

import re
from typing import Any

import pytest
from pytest_bdd import given, when, then, parsers

from tool_selector_mcp.corpus import Agent, Corpus, Tool
from tool_selector_mcp.retrieval import rewrite_query, search


def _state(bdd_state: dict) -> dict:
    return bdd_state.setdefault("retrieval", {})


def _empty_agent(agent_id: str, description: str) -> Agent:
    return Agent(
        agent_id=agent_id,
        description=description,
        command="echo",
        args=(),
        env={},
        tools=(),
    )


# --- Background: build the catalog from data tables ----------------------


@given("a catalog containing the following agents:")
def _catalog_agents(datatable, bdd_state: dict) -> None:
    state = _state(bdd_state)
    agents: dict[str, Agent] = {}
    header, *rows = datatable
    columns = {col: i for i, col in enumerate(header)}
    for row in rows:
        agent_id = row[columns["agent_id"]]
        description = row[columns["description"]]
        agents[agent_id] = _empty_agent(agent_id, description)
    state["agents"] = agents


@given("the catalog contains the following tools:")
def _catalog_tools(datatable, bdd_state: dict) -> None:
    state = _state(bdd_state)
    agents = state["agents"]
    header, *rows = datatable
    columns = {col: i for i, col in enumerate(header)}
    tools_by_owner: dict[str, list[Tool]] = {agent_id: [] for agent_id in agents}
    for row in rows:
        tool_id = row[columns["tool_id"]]
        description = row[columns["description"]]
        owner = row[columns["owner"]]
        tools_by_owner.setdefault(owner, []).append(
            Tool(name=tool_id, description=description)
        )
    new_agents: dict[str, Agent] = {}
    for agent_id, agent in agents.items():
        new_agents[agent_id] = Agent(
            agent_id=agent.agent_id,
            description=agent.description,
            command=agent.command,
            args=agent.args,
            env=agent.env,
            tools=tuple(tools_by_owner.get(agent_id, [])),
        )
    state["agents"] = new_agents
    state["corpus"] = Corpus(agents=new_agents)


# --- Additional Given steps used by some scenarios ----------------------


@given(parsers.parse('an additional agent "{agent_id}" described as "{description}"'))
def _additional_agent(agent_id: str, description: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    state["agents"][agent_id] = _empty_agent(agent_id, description)
    state["corpus"] = Corpus(agents=state["agents"])


@given(
    parsers.parse(
        '"{agent_id}" has a tool "{tool_name}" described as "{description}"'
    )
)
def _additional_tool(
    agent_id: str, tool_name: str, description: str, bdd_state: dict
) -> None:
    state = _state(bdd_state)
    agent = state["agents"][agent_id]
    new_agent = Agent(
        agent_id=agent.agent_id,
        description=agent.description,
        command=agent.command,
        args=agent.args,
        env=agent.env,
        tools=tuple(list(agent.tools) + [Tool(name=tool_name, description=description)]),
    )
    state["agents"][agent_id] = new_agent
    state["corpus"] = Corpus(agents=state["agents"])


@given(parsers.parse('the multi-step query "{query}"'))
def _multi_step_query(query: str, bdd_state: dict) -> None:
    _state(bdd_state)["multi_step_query"] = query


@given(parsers.parse('the user query is "{query}"'))
def _user_query(query: str, bdd_state: dict) -> None:
    _state(bdd_state)["user_query"] = query


@given("query rewriting is disabled")
def _rewrite_disabled(bdd_state: dict) -> None:
    _state(bdd_state)["rewrite"] = False


# --- When steps ----------------------------------------------------------


@when(
    parsers.parse(
        'the query "{query}" is submitted directly with K={k:d}'
    )
)
def _query_submitted_directly(query: str, k: int, bdd_state: dict) -> None:
    state = _state(bdd_state)
    rewrite = state.get("rewrite", True)
    state["results"] = search(state["corpus"], query, k=k, rewrite=rewrite)


@when(parsers.parse('the query "{query}" is submitted with K={k:d}'))
def _query_submitted_with_k(query: str, k: int, bdd_state: dict) -> None:
    state = _state(bdd_state)
    rewrite = state.get("rewrite", True)
    state["results"] = search(state["corpus"], query, k=k, rewrite=rewrite)


@when("the query is decomposed into sub-tasks:")
def _decompose_subtasks(datatable, bdd_state: dict) -> None:
    state = _state(bdd_state)
    header, *rows = datatable
    columns = {col: i for i, col in enumerate(header)}
    state["sub_queries"] = [row[columns["sub_query"]] for row in rows]


@when("each sub-query is submitted independently to the retrieval algorithm")
def _submit_sub_queries(bdd_state: dict) -> None:
    state = _state(bdd_state)
    rewrite = state.get("rewrite", True)
    state["sub_results"] = [
        search(state["corpus"], q, k=1, rewrite=rewrite)
        for q in state["sub_queries"]
    ]


@when("the retrieval pipeline runs stage 1 (LLM query rewrite)")
def _run_stage_one(bdd_state: dict) -> None:
    state = _state(bdd_state)
    state["rewritten"] = rewrite_query(state["user_query"])


# --- Then steps ----------------------------------------------------------


@then(parsers.parse('the top result is the agent "{agent_id}"'))
def _top_result(agent_id: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    results = state.get("results") or state.get("stage_two_results")
    assert results, "no results recorded"
    assert results[0].agent_id == agent_id, f"top was {results[0].agent_id}"


@then(parsers.parse('"{agent_id}" is returned in the results'))
def _agent_in_results(agent_id: str, bdd_state: dict) -> None:
    results = _state(bdd_state).get("results") or _state(bdd_state).get("stage_two_results")
    assert results, "no results recorded"
    assert agent_id in {r.agent_id for r in results}


@then(parsers.parse('"{agent_id}" appears exactly once in the results'))
def _agent_appears_once(agent_id: str, bdd_state: dict) -> None:
    results = _state(bdd_state)["results"]
    count = sum(1 for r in results if r.agent_id == agent_id)
    assert count == 1, f"{agent_id} appeared {count} times; results={results}"


@then(parsers.parse('step {step:d} returns "{agent_id}" as the top agent'))
def _step_top_agent(step: int, agent_id: str, bdd_state: dict) -> None:
    results = _state(bdd_state)["sub_results"][step - 1]
    assert results, f"no results for step {step}"
    assert results[0].agent_id == agent_id


@then("the combined result covers both required agents")
def _combined_covers_both(bdd_state: dict) -> None:
    sub_results = _state(bdd_state)["sub_results"]
    combined = {r.agent_id for sub in sub_results for r in sub}
    assert {"github-mcp", "slack-mcp"} <= combined


@then(
    parsers.re(
        r'the query is condensed to keywords focused on the action and target,'
        r' e\.g\. "(?P<example>[^"]+)"'
    )
)
def _query_condensed(example: str, bdd_state: dict) -> None:
    state = _state(bdd_state)
    rewritten = state["rewritten"]
    original = state["user_query"]

    rewritten_tokens = rewritten.split()
    original_tokens = re.findall(r"[a-z0-9]+", original.lower())
    assert len(rewritten_tokens) < len(original_tokens), (
        f"rewrite did not condense: {original!r} -> {rewritten!r}"
    )

    # The example calls out the core action and target keywords; require the
    # rewrite to retain those exact tokens.
    for keyword in example.split():
        assert keyword in rewritten_tokens, (
            f"missing keyword {keyword!r} in rewrite {rewritten!r}"
        )


@then("the condensed query is passed to stage 2 (embedding similarity search)")
def _passed_to_stage_two(bdd_state: dict) -> None:
    state = _state(bdd_state)
    rewritten = state["rewritten"]
    # Stage 2: re-run the search but pass the already-rewritten query and
    # disable a second pass of rewriting, so the test observes that the
    # condensed query is what reaches the similarity step.
    state["stage_two_results"] = search(
        state["corpus"], rewritten, k=1, rewrite=False
    )


@then("the embedding search runs directly on the raw query")
def _search_on_raw(bdd_state: dict) -> None:
    state = _state(bdd_state)
    assert state.get("rewrite") is False, "rewrite flag was not disabled"
    assert state.get("results") is not None, "search was not executed"
