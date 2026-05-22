"""Step definitions for docs/features/algorithms/embedding-interface.feature.

Also provides the shared When/Then steps used by all embedding feature files
(scripted, anthropic, all-minilm-l6-v2), since pytest-bdd's step registry is
global and each step text may only have one registered implementation.

All embedding step modules store their state under bdd_state["emb_test"] so
these shared steps can serve every embedding scenario.
"""

from __future__ import annotations

from pytest_bdd import given, when, then


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("emb_test", {})


# ---------------------------------------------------------------------------
# Given – embedding interface scenarios
# ---------------------------------------------------------------------------


@given("an embedding implementation")
def _embedding_impl(bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import TokenOverlapEmbedding
    _s(bdd_state)["embedding"] = TokenOverlapEmbedding()


@given("no embedding is explicitly configured")
def _no_embedding(bdd_state: dict) -> None:
    from tool_selector_mcp.corpus import Agent, Corpus, Tool

    agents = {
        "github-mcp": Agent(
            agent_id="github-mcp",
            description="Interact with GitHub repositories",
            command="echo",
            args=(),
            env={},
            tools=(Tool(name="create_pull_request", description="Open a new pull request on a GitHub repository"),),
        )
    }
    _s(bdd_state)["corpus"] = Corpus(agents=agents)
    _s(bdd_state)["embedding"] = None


# ---------------------------------------------------------------------------
# Shared When steps – used by embedding-interface, anthropic, and minilm
# ---------------------------------------------------------------------------


@when("it scores the query \"open a pull request\" against \"Open a new pull request on GitHub\"")
def _score_specific(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    _s(bdd_state)["score"] = emb(
        "open a pull request", "Open a new pull request on GitHub"
    )


@when("it scores any query against any target text")
def _score_any(bdd_state: dict) -> None:
    emb = _s(bdd_state).get("embedding")
    if emb is None:
        from tool_selector_mcp.retrieval import search
        corpus = _s(bdd_state)["corpus"]
        results = search(corpus, "open a pull request", k=1)
        _s(bdd_state)["search_results"] = results
        _s(bdd_state)["score"] = float(results[0].score) if results else 0.0
    else:
        _s(bdd_state)["score"] = emb("test query", "some target text")


@when("it scores multiple query-text pairs in sequence")
def _score_multiple(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    _s(bdd_state)["score"] = emb("query one", "text one")
    emb("query two", "text two")
    emb("query three", "text three")


@when("the retrieval algorithm runs a query against the catalog")
def _run_retrieval(bdd_state: dict) -> None:
    from tool_selector_mcp.retrieval import search
    corpus = _s(bdd_state)["corpus"]
    _s(bdd_state)["search_results"] = search(corpus, "open a pull request", k=1)


# ---------------------------------------------------------------------------
# Shared Then steps – used by all embedding feature files
# ---------------------------------------------------------------------------


@then("it returns a float score")
def _returns_float(bdd_state: dict) -> None:
    score = _s(bdd_state)["score"]
    assert isinstance(score, float), f"expected float, got {type(score).__name__}"


@then("the score is between 0.0 and 1.0 inclusive")
def _score_in_range(bdd_state: dict) -> None:
    score = _s(bdd_state)["score"]
    assert 0.0 <= score <= 1.0, f"score {score} out of [0.0, 1.0]"


@then("similarity is computed using the token-overlap embedding")
def _uses_token_overlap(bdd_state: dict) -> None:
    from tool_selector_mcp.retrieval import search

    corpus = _s(bdd_state)["corpus"]
    results = _s(bdd_state).get("search_results") or search(corpus, "open a pull request", k=1)
    expected = search(corpus, "open a pull request", k=1)
    assert [r.agent_id for r in results] == [r.agent_id for r in expected]
    assert results and results[0].agent_id == "github-mcp"
