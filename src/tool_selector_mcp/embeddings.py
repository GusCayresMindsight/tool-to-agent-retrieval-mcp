"""Embedding implementations for tool-selector-mcp.

An Embedding is any callable (query: str, text: str) -> float that returns
a similarity score in [0.0, 1.0].  Higher means more similar.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedding(Protocol):
    def __call__(self, query: str, text: str) -> float: ...


class TokenOverlapEmbedding:
    """Default embedding: Jaccard-style token overlap between query and text."""

    def __call__(self, query: str, text: str) -> float:
        from .retrieval import _keywords, _score

        return _score(_keywords(query), text)


class ScriptedEmbedding:
    """Assigns fixed scores to specific texts via an explicit lookup table.

    Any text not in the table returns ``default``.  The score is independent
    of the query — useful for wiring deterministic behavior in tests.
    """

    def __init__(
        self,
        scores: dict[str, float] | None = None,
        default: float = 0.0,
    ) -> None:
        self._scores: dict[str, float] = dict(scores or {})
        self._default = default
        self._calls: list[tuple[str, str]] = []

    def __call__(self, query: str, text: str) -> float:
        self._calls.append((query, text))
        raw = self._scores.get(text, self._default)
        return min(1.0, max(0.0, float(raw)))

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def called_texts(self) -> list[str]:
        return [text for _, text in self._calls]


class AnthropicEmbedding:
    """Scores semantic similarity by prompting Claude via the Anthropic messages API.

    Requires an ``ANTHROPIC_API_KEY`` environment variable (or explicit key).
    """

    def __init__(self, api_key: str | None = None, *, client=None) -> None:
        if client is not None:
            self._client = client
        else:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)

    def __call__(self, query: str, text: str) -> float:
        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Rate how relevant this text is to the query. "
                        "Respond with only a float between 0.0 and 1.0.\n"
                        f"Query: {query}\nText: {text}"
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        return min(1.0, max(0.0, float(raw)))


class AllMiniLML6V2Embedding:
    """Dense vector embedding using sentence-transformers all-MiniLM-L6-v2.

    The model is loaded lazily on first use and reused for all subsequent calls.
    Similarity is cosine similarity, rescaled from [-1, 1] to [0.0, 1.0].
    """

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def __call__(self, query: str, text: str) -> float:
        import numpy as np

        model = self._get_model()
        vecs = model.encode([query, text], normalize_embeddings=True)
        sim = float(np.dot(vecs[0], vecs[1]))
        return min(1.0, max(0.0, (sim + 1.0) / 2.0))
