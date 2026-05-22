"""Tool-to-Agent retrieval.

Implements the unified-catalog approach from Lumer et al. (arXiv:2511.01854v2):
agents and tools share a single retrieval index, results are deduplicated per
agent, and a two-stage pipeline rewrites the query into focused keywords
before similarity search.

The "embedding" step is approximated with token-overlap scoring so the
behavior is deterministic and dependency-free; the structure (rewrite ->
score over CT u CA -> dedupe by agent -> top-K) matches the paper.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .corpus import Corpus

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "with",
        "is", "are", "be", "by", "as", "at", "this", "that",
        "i", "we", "you", "me", "my", "your", "us",
        "hey", "can", "could", "would", "should",
        "go", "going", "gone", "ahead", "up", "out",
        "please", "thanks", "ok", "okay",
        "do", "does", "did", "have", "has", "had",
        "it", "its", "they", "them", "their",
    }
)


@dataclass(frozen=True)
class RetrievalResult:
    agent_id: str
    score: float
    matched_via: str  # "agent" or "tool"
    tool_name: str | None = None


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _keywords(text: str) -> set[str]:
    return {tok for tok in _tokenize(text) if tok not in STOPWORDS}


def rewrite_query(query: str) -> str:
    """Stage 1: condense a free-text query into focused keywords.

    Removes filler words so the resulting string is a compact sequence of
    content tokens for downstream similarity search.
    """
    tokens = [tok for tok in _tokenize(query) if tok not in STOPWORDS]
    return " ".join(tokens)


def _score(query_keywords: set[str], target_text: str) -> float:
    target = _keywords(target_text)
    if not query_keywords or not target:
        return 0.0
    overlap = query_keywords & target
    return len(overlap) / len(query_keywords)


@dataclass(frozen=True)
class SearchInfo:
    """Extended search result including algorithm diagnostics."""

    results: list[RetrievalResult]
    candidates_evaluated: int
    total_catalog_size: int


def search_with_info(
    corpus: Corpus,
    query: str,
    k: int = 1,
    *,
    rewrite: bool = True,
    embedding: Any | None = None,
    n: int | None = None,
) -> SearchInfo:
    """Algorithm 1 from Lumer et al. with full diagnostics.

    Scores every entry in CT ∪ CA, takes the top-N candidates, then
    iterates in score order — resolving tool entries to their owner agent —
    stopping as soon as K unique agents are collected or the pool is exhausted.

    Returns a :class:`SearchInfo` with the result list and the number of
    candidates actually evaluated (useful for verifying early exit).
    """
    from .embeddings import TokenOverlapEmbedding

    effective_query = rewrite_query(query) if rewrite else query

    if embedding is None:
        embedding = TokenOverlapEmbedding()

    # Score all entries in CT ∪ CA
    scored: list[tuple[float, str, Any, Any]] = []
    for agent in corpus.agents.values():
        agent_text = f"{agent.agent_id} {agent.description}"
        scored.append((embedding(effective_query, agent_text), agent.agent_id, agent, None))
        for tool in agent.tools:
            tool_text = f"{tool.name} {tool.description}"
            scored.append((embedding(effective_query, tool_text), tool.name, agent, tool))

    # Sort descending by score, then ascending by name for determinism
    scored.sort(key=lambda x: (-x[0], x[1]))

    total = len(scored)
    candidates = scored[:n] if n is not None else scored

    # Deduplication loop (Algorithm 1, lines 3-14)
    seen: set[str] = set()
    results: list[RetrievalResult] = []
    candidates_evaluated = 0

    for score, _, agent, tool in candidates:
        candidates_evaluated += 1
        if tool is not None:
            result = RetrievalResult(
                agent_id=agent.agent_id,
                score=score,
                matched_via="tool",
                tool_name=tool.name,
            )
        else:
            result = RetrievalResult(
                agent_id=agent.agent_id,
                score=score,
                matched_via="agent",
            )

        if score > 0 and result.agent_id not in seen:
            seen.add(result.agent_id)
            results.append(result)

        if len(results) == k:
            break

    return SearchInfo(
        results=results,
        candidates_evaluated=candidates_evaluated,
        total_catalog_size=total,
    )


def search(
    corpus: Corpus,
    query: str,
    k: int = 1,
    *,
    rewrite: bool = True,
) -> list[RetrievalResult]:
    """Return up to ``k`` agents ranked by best match across CT ∪ CA.

    When ``rewrite`` is ``True`` the query is first condensed via
    :func:`rewrite_query`. Multiple high-scoring entries belonging to the
    same agent collapse to a single result for that agent.
    """
    effective_query = rewrite_query(query) if rewrite else query
    query_kw = _keywords(effective_query)
    best_per_agent: dict[str, RetrievalResult] = {}

    for agent in corpus.agents.values():
        agent_text = f"{agent.agent_id} {agent.description}"
        agent_score = _score(query_kw, agent_text)
        best = RetrievalResult(
            agent_id=agent.agent_id,
            score=agent_score,
            matched_via="agent",
        )
        for tool in agent.tools:
            tool_text = f"{tool.name} {tool.description}"
            tool_score = _score(query_kw, tool_text)
            if tool_score > best.score:
                best = RetrievalResult(
                    agent_id=agent.agent_id,
                    score=tool_score,
                    matched_via="tool",
                    tool_name=tool.name,
                )
        best_per_agent[agent.agent_id] = best

    ranked = sorted(
        (r for r in best_per_agent.values() if r.score > 0),
        key=lambda r: (-r.score, r.agent_id),
    )
    return ranked[:k]
