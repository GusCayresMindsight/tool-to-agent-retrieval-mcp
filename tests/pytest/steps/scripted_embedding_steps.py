"""Step definitions for docs/features/algorithms/embeddings/scripted.feature.

Shared When/Then steps ("it scores any query against any target text",
"it returns a float score", "the score is between 0.0 and 1.0 inclusive")
are defined in embedding_interface_steps.py and work for this module because
all embedding modules share bdd_state["emb_test"] as the state key.
"""

from __future__ import annotations

from pytest_bdd import given, when, then, parsers


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("emb_test", {})


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("a scripted embedding configured with:")
def _scripted_from_table(datatable, bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import ScriptedEmbedding

    header, *rows = datatable
    columns = {col: i for i, col in enumerate(header)}
    scores = {
        row[columns["text"]]: float(row[columns["score"]])
        for row in rows
    }
    _s(bdd_state)["embedding"] = ScriptedEmbedding(scores=scores)


@given(parsers.parse("a scripted embedding with default score {default:g}"))
def _scripted_with_default(default: float, bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import ScriptedEmbedding

    _s(bdd_state)["embedding"] = ScriptedEmbedding(default=default)


@given("a scripted embedding configured with a fixed score for a target text")
def _scripted_fixed_score(bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import ScriptedEmbedding

    target = "Open a new pull request on a GitHub repository"
    _s(bdd_state)["embedding"] = ScriptedEmbedding(scores={target: 0.9})
    _s(bdd_state)["fixed_target"] = target


@given("a scripted embedding")
def _scripted_bare(bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import ScriptedEmbedding

    _s(bdd_state)["embedding"] = ScriptedEmbedding(
        scores={"known text": 0.7}, default=0.3
    )


# ---------------------------------------------------------------------------
# Scripted-specific When steps
# ---------------------------------------------------------------------------


@when("it scores any query against \"Open a new pull request on a GitHub repository\"")
def _score_known_text(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    _s(bdd_state)["score"] = emb("any query", "Open a new pull request on a GitHub repository")


@when("it scores any query against a text that is not in the lookup table")
def _score_unknown_text(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    _s(bdd_state)["score"] = emb("any query", "__not_in_table__")


@when("the same target text is scored against two different queries")
def _score_two_queries(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    target = _s(bdd_state)["fixed_target"]
    _s(bdd_state)["score_a"] = emb("first query", target)
    _s(bdd_state)["score_b"] = emb("second query", target)
    # also store one of them as "score" for shared Then checks
    _s(bdd_state)["score"] = _s(bdd_state)["score_a"]


# ---------------------------------------------------------------------------
# Scripted-specific Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("it returns {expected:g}"))
def _returns_value(expected: float, bdd_state: dict) -> None:
    score = _s(bdd_state)["score"]
    assert score == expected, f"expected {expected}, got {score}"


@then("both calls return the same score")
def _same_score(bdd_state: dict) -> None:
    s = _s(bdd_state)
    assert s["score_a"] == s["score_b"], (
        f"scores differ: {s['score_a']} vs {s['score_b']}"
    )
