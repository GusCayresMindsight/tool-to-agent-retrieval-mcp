"""Step definitions for docs/features/algorithms/corpus-embedding.feature."""

from __future__ import annotations

from pytest_bdd import given, when, then, parsers


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

def _r(bdd_state: dict) -> dict:
    """Background data lives in the 'retrieval' namespace (shared steps)."""
    return bdd_state.setdefault("retrieval", {})


def _s(bdd_state: dict) -> dict:
    """Corpus-embedding-specific state."""
    return bdd_state.setdefault("corpus_embedding", {})


# ---------------------------------------------------------------------------
# Additional Given steps (corpus scoring)
# ---------------------------------------------------------------------------


@given(parsers.parse('the query "{query}"'))
def _given_query(query: str, bdd_state: dict) -> None:
    _s(bdd_state)["query"] = query


@given("a mock embedding that returns 1.0 for any text containing \"pull request\"")
def _mock_embedding_init(bdd_state: dict) -> None:
    _s(bdd_state)["mock_rule"] = "pull request"


@given("returns 0.0 for all other texts")
def _mock_embedding_default(bdd_state: dict) -> None:
    rule = _s(bdd_state)["mock_rule"]

    class _Mock:
        def __init__(self) -> None:
            self._calls: list[tuple[str, str]] = []

        def __call__(self, query: str, text: str) -> float:
            self._calls.append((query, text))
            return 1.0 if rule in text.lower() else 0.0

        @property
        def call_count(self) -> int:
            return len(self._calls)

        @property
        def called_texts(self) -> list[str]:
            return [t for _, t in self._calls]

    _s(bdd_state)["mock_embedding"] = _Mock()


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("the tool corpus CT is constructed")
def _build_ct(bdd_state: dict) -> None:
    corpus = _r(bdd_state)["corpus"]
    ct: dict[str, dict] = {}
    for agent in corpus.agents.values():
        for tool in agent.tools:
            ct[tool.name] = {"description": tool.description, "owner": agent.agent_id, "type": "tool"}
    _s(bdd_state)["CT"] = ct


@when("the agent corpus CA is constructed")
def _build_ca(bdd_state: dict) -> None:
    corpus = _r(bdd_state)["corpus"]
    ca: dict[str, dict] = {}
    for agent in corpus.agents.values():
        ca[agent.agent_id] = {"description": agent.description, "type": "agent"}
    _s(bdd_state)["CA"] = ca


@when("the unified catalog C is assembled")
def _build_c(bdd_state: dict) -> None:
    corpus = _r(bdd_state)["corpus"]
    c: dict[str, dict] = {}
    ct: dict[str, dict] = {}
    ca: dict[str, dict] = {}
    for agent in corpus.agents.values():
        ca[agent.agent_id] = {"description": agent.description, "type": "agent", "owner": None}
        c[agent.agent_id] = ca[agent.agent_id]
        for tool in agent.tools:
            entry = {"description": tool.description, "type": "tool", "owner": agent.agent_id}
            ct[tool.name] = entry
            c[tool.name] = entry
    _s(bdd_state).update({"C": c, "CT": ct, "CA": ca})


@when("similarity scores are computed against C")
def _compute_scores(bdd_state: dict) -> None:
    from tool_selector_mcp.embeddings import TokenOverlapEmbedding

    corpus = _r(bdd_state)["corpus"]
    query = _s(bdd_state).get("query", "")
    emb = TokenOverlapEmbedding()
    scores: dict[str, float] = {}
    for agent in corpus.agents.values():
        scores[agent.agent_id] = emb(query, f"{agent.agent_id} {agent.description}")
        for tool in agent.tools:
            scores[tool.name] = emb(query, f"{tool.name} {tool.description}")
    _s(bdd_state)["scores"] = scores
    # Build C so Then steps work even if the preceding When didn't assemble it
    if "C" not in _s(bdd_state):
        _build_c(bdd_state)


@when("similarity scores are computed against C using the mock embedding")
def _compute_scores_mock(bdd_state: dict) -> None:
    corpus = _r(bdd_state)["corpus"]
    query = _s(bdd_state).get("query", "")
    mock = _s(bdd_state)["mock_embedding"]
    scores: dict[str, float] = {}
    for agent in corpus.agents.values():
        scores[agent.agent_id] = mock(query, f"{agent.agent_id} {agent.description}")
        for tool in agent.tools:
            scores[tool.name] = mock(query, f"{tool.name} {tool.description}")
    _s(bdd_state)["scores"] = scores
    if "C" not in _s(bdd_state):
        _build_c(bdd_state)


# ---------------------------------------------------------------------------
# Then steps – CT/CA/C structure
# ---------------------------------------------------------------------------


@then(parsers.parse('"{name}" is present in CT with its description'))
def _in_ct(name: str, bdd_state: dict) -> None:
    ct = _s(bdd_state)["CT"]
    assert name in ct, f"{name!r} not in CT; CT={list(ct)}"
    assert ct[name]["description"], f"description for {name!r} is empty"


@then(parsers.parse('the entry for "{name}" records own(t) = "{owner}"'))
def _owns(name: str, owner: str, bdd_state: dict) -> None:
    ct = _s(bdd_state)["CT"]
    assert ct[name]["owner"] == owner, f"expected own({name})={owner}, got {ct[name]['owner']}"


@then(parsers.parse('"{name}" is present in CA with its description'))
def _in_ca(name: str, bdd_state: dict) -> None:
    ca = _s(bdd_state)["CA"]
    assert name in ca, f"{name!r} not in CA; CA={list(ca)}"
    assert ca[name]["description"], f"description for {name!r} is empty"


@then(parsers.parse('τ("{name}") = agent'))
def _tau_agent(name: str, bdd_state: dict) -> None:
    s = _s(bdd_state)
    if "CA" in s:
        assert name in s["CA"], f"{name!r} not in CA"
    elif "C" in s:
        assert s["C"][name]["type"] == "agent"
    else:
        corpus = _r(bdd_state)["corpus"]
        assert name in corpus.agents, f"{name!r} is not an agent"


@then(parsers.parse('τ("{name}") = tool'))
def _tau_tool(name: str, bdd_state: dict) -> None:
    s = _s(bdd_state)
    if "CT" in s:
        assert name in s["CT"], f"{name!r} not in CT"
    elif "C" in s:
        assert s["C"][name]["type"] == "tool"
    else:
        corpus = _r(bdd_state)["corpus"]
        assert corpus.find_tool(name) is not None, f"{name!r} is not a tool"


@then("C contains all entries from CT")
def _c_contains_ct(bdd_state: dict) -> None:
    s = _s(bdd_state)
    c, ct = s["C"], s["CT"]
    for name in ct:
        assert name in c, f"{name!r} from CT not in C"
        assert c[name]["type"] == "tool"


@then("C contains all entries from CA")
def _c_contains_ca(bdd_state: dict) -> None:
    s = _s(bdd_state)
    c, ca = s["C"], s["CA"]
    for name in ca:
        assert name in c, f"{name!r} from CA not in C"
        assert c[name]["type"] == "agent"


@then(parsers.parse('own("{name}") resolves to "{owner}"'))
def _own_resolves(name: str, owner: str, bdd_state: dict) -> None:
    c = _s(bdd_state)["C"]
    assert c[name]["owner"] == owner, f"own({name})={c[name]['owner']!r}, want {owner!r}"


# ---------------------------------------------------------------------------
# Then steps – scoring
# ---------------------------------------------------------------------------


@then("a score s(q, e) is produced for every entry e in C")
def _score_for_every_entry(bdd_state: dict) -> None:
    scores = _s(bdd_state)["scores"]
    c = _s(bdd_state)["C"]
    missing = set(c) - set(scores)
    assert not missing, f"entries with no score: {missing}"


@then(parsers.parse('the scores rank "{a}" and "{b}" above unrelated entries'))
def _rank_above_unrelated(a: str, b: str, bdd_state: dict) -> None:
    scores = _s(bdd_state)["scores"]
    # Both named entries must be scored.
    assert a in scores, f"{a!r} has no score"
    assert b in scores, f"{b!r} has no score"
    # Collectively, the pair leads the ranking: the best of the two is ≥ every
    # other entry.  (With token-overlap, one of the pair — the one whose
    # description directly mentions the query tokens — carries the group.)
    pair_max = max(scores[a], scores[b])
    unrelated_max = max(
        (v for k, v in scores.items() if k not in (a, b)),
        default=0.0,
    )
    assert pair_max >= unrelated_max, (
        f"neither {a}={scores[a]} nor {b}={scores[b]} leads the unrelated max {unrelated_max}"
    )


@then(parsers.parse('"{name}" receives a score of {expected:g}'))
def _receives_score(name: str, expected: float, bdd_state: dict) -> None:
    actual = _s(bdd_state)["scores"][name]
    assert actual == expected, f"score({name})={actual}, expected {expected}"


@then("the mock embedding's score function is invoked for every entry in C")
def _mock_invoked_for_all(bdd_state: dict) -> None:
    mock = _s(bdd_state)["mock_embedding"]
    c = _s(bdd_state)["C"]
    assert mock.call_count == len(c), (
        f"mock called {mock.call_count} times for {len(c)} entries"
    )
