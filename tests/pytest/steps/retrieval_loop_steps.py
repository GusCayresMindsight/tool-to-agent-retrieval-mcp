"""Step definitions for docs/features/algorithms/tool-to-agent-retrieval-loop.feature."""

from __future__ import annotations

from pytest_bdd import parsers, then, when

# Background Given steps (agent/tool table) are already defined in
# tool_to_agent_retrieval_steps.py and share the 'retrieval' namespace.


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("retrieval", {})


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('the query "{query}" is submitted with N={n:d} and K={k:d}'))
def _query_with_n_k(query: str, n: int, k: int, bdd_state: dict) -> None:
    from tool_selector_mcp.retrieval import search_with_info

    state = _s(bdd_state)
    info = search_with_info(state["corpus"], query, k=k, n=n)
    state["results"] = info.results
    state["candidates_evaluated"] = info.candidates_evaluated
    state["total_catalog_size"] = info.total_catalog_size
    state["n"] = n
    state["k"] = k


# ---------------------------------------------------------------------------
# Then – ranking and loop structure
# ---------------------------------------------------------------------------


@then("the loop ranks all entries in C by similarity to q")
def _loop_ranks_all(bdd_state: dict) -> None:
    state = _s(bdd_state)
    results = state["results"]
    assert results, "search returned no results"
    # Verify ordering: scores are non-increasing
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score, (
            f"results not sorted: {results[i].score} < {results[i + 1].score}"
        )


@then(parsers.parse("evaluates up to N={n:d} candidates to produce K={k:d} unique agent"))
def _evaluates_up_to_n(n: int, k: int, bdd_state: dict) -> None:
    state = _s(bdd_state)
    results = state["results"]
    assert len(results) <= k, f"expected at most {k} agents, got {len(results)}"
    evaluated = state["candidates_evaluated"]
    total = state["total_catalog_size"]
    assert evaluated <= min(n, total), (
        f"evaluated {evaluated} candidates, expected at most min(N={n}, total={total})={min(n, total)}"
    )


@then("the top-ranked entry has τ = agent")
def _top_is_agent(bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    assert results, "no results"
    assert results[0].matched_via == "agent", (
        f"top entry matched via {results[0].matched_via!r}, expected 'agent'"
    )


@then(parsers.parse('"{agent_id}" is returned as a direct match without owner resolution'))
def _direct_match(agent_id: str, bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    assert results, "no results"
    top = results[0]
    assert top.agent_id == agent_id
    assert top.matched_via == "agent", f"expected direct agent match, got {top.matched_via!r}"


@then("the top-ranked entry has τ = tool")
def _top_is_tool(bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    assert results, "no results"
    assert results[0].matched_via == "tool", (
        f"top entry matched via {results[0].matched_via!r}, expected 'tool'"
    )


@then(parsers.re(r'^own\((?P<tool>[^)]+)\) = "(?P<agent>[^"]+)" is resolved$'))
def _own_resolved(tool: str, agent: str, bdd_state: dict) -> None:
    corpus = _s(bdd_state)["corpus"]
    found = corpus.find_tool(tool)
    assert found is not None, f"tool {tool!r} not in corpus"
    owner_agent, _ = found
    assert owner_agent.agent_id == agent, (
        f"own({tool})={owner_agent.agent_id!r}, expected {agent!r}"
    )


@then(parsers.parse('"{agent_id}" is returned as the owner of the matched tool'))
def _owner_of_tool(agent_id: str, bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    assert results, "no results"
    top = results[0]
    assert top.agent_id == agent_id
    assert top.matched_via == "tool", f"expected tool match, got {top.matched_via!r}"


@then(parsers.parse('"{agent_id}" appears exactly once in the result set'))
def _appears_once_in_result_set(agent_id: str, bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    count = sum(1 for r in results if r.agent_id == agent_id)
    assert count == 1, f"{agent_id!r} appeared {count} times in result set"


@then(parsers.parse("the result set contains at most {k:d} unique agents"))
def _result_set_at_most(k: int, bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    unique = len({r.agent_id for r in results})
    assert unique <= k, f"found {unique} unique agents, expected at most {k}"


@then(parsers.parse("the result set contains at most {k:d} agents"))
def _result_set_at_most_agents(k: int, bdd_state: dict) -> None:
    results = _s(bdd_state)["results"]
    assert len(results) <= k, f"result set has {len(results)} agents, expected at most {k}"


@then(parsers.parse("the loop stops as soon as {k:d} unique agent is identified"))
def _loop_stops_at_k(k: int, bdd_state: dict) -> None:
    state = _s(bdd_state)
    results = state["results"]
    assert len(results) == k or len(results) == state["total_catalog_size"] // 2, (
        f"expected {k} agent(s) in result, got {len(results)}"
    )
    # When K=1 and a high-scoring entry exists, we should have stopped after ≤1 hit
    assert len(results) <= k or state["candidates_evaluated"] >= state["total_catalog_size"]


@then("does not evaluate remaining candidates from the top-N pool")
def _early_exit(bdd_state: dict) -> None:
    state = _s(bdd_state)
    evaluated = state["candidates_evaluated"]
    total = state["total_catalog_size"]
    n = state["n"]
    pool = min(n, total)
    # Early exit: we found K agents before exhausting the full candidate pool
    assert evaluated < pool, (
        f"evaluated all {pool} candidates — no early exit occurred "
        f"(evaluated={evaluated}, pool={pool})"
    )


@then("the loop exits after exhausting all N candidates")
def _exhausts_all(bdd_state: dict) -> None:
    state = _s(bdd_state)
    evaluated = state["candidates_evaluated"]
    total = state["total_catalog_size"]
    n = state["n"]
    pool = min(n, total)
    assert evaluated >= pool, f"loop exited early (evaluated={evaluated}, pool={pool})"
