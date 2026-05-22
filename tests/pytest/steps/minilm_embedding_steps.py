"""Step definitions for docs/features/algorithms/embeddings/all-minilm-l6-v2.feature.

Shared When/Then steps are defined in embedding_interface_steps.py.
All embedding modules share bdd_state["emb_test"] as the state key.

Both `numpy` and `sentence_transformers` are mocked so these tests run
without those packages installed.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, then


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("emb_test", {})


class _FakeNumpy:
    """Minimal numpy stand-in for AllMiniLML6V2Embedding.__call__."""

    def dot(self, a, b) -> float:
        return float(sum(x * y for x, y in zip(a, b)))


def _make_mock_model() -> MagicMock:
    """Mock SentenceTransformer that returns unit vectors → cosine sim = 1.0."""
    model = MagicMock()
    # Two identical unit vectors: dot product = 1.0 → score = (1+1)/2 = 1.0
    model.encode.return_value = [[1.0, 0.0], [1.0, 0.0]]
    return model


def _setup_mocks(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, _FakeNumpy]:
    """Inject fake numpy and sentence_transformers into sys.modules."""
    fake_np = _FakeNumpy()
    mock_model = _make_mock_model()
    fake_st = MagicMock()
    fake_st.SentenceTransformer.return_value = mock_model

    monkeypatch.setitem(sys.modules, "numpy", fake_np)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    return mock_model, fake_np


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an All-MiniLM-L6-v2 embedding")
def _minilm_bare(monkeypatch: pytest.MonkeyPatch, bdd_state: dict) -> None:
    mock_model, fake_np = _setup_mocks(monkeypatch)

    from tool_selector_mcp.embeddings import AllMiniLML6V2Embedding
    emb = AllMiniLML6V2Embedding()
    emb._model = mock_model

    _s(bdd_state)["embedding"] = emb
    _s(bdd_state)["mock_model"] = mock_model
    _s(bdd_state)["fake_np"] = fake_np


@given("an All-MiniLM-L6-v2 embedding instantiated once")
def _minilm_single_instance(monkeypatch: pytest.MonkeyPatch, bdd_state: dict) -> None:
    mock_model, fake_np = _setup_mocks(monkeypatch)

    from tool_selector_mcp.embeddings import AllMiniLML6V2Embedding
    emb = AllMiniLML6V2Embedding()
    emb._model = mock_model

    _s(bdd_state)["embedding"] = emb
    _s(bdd_state)["mock_model"] = mock_model
    _s(bdd_state)["fake_np"] = fake_np


# ---------------------------------------------------------------------------
# Then – MiniLM-specific assertions
# ---------------------------------------------------------------------------


@then("it encodes both strings into dense vectors")
def _encodes_both(bdd_state: dict) -> None:
    mock_model = _s(bdd_state)["mock_model"]
    assert mock_model.encode.called, "model.encode was not called"
    call_args = mock_model.encode.call_args_list[-1]
    texts = call_args[0][0]
    assert len(texts) == 2, f"expected 2 texts to encode, got {len(texts)}"


@then("returns their cosine similarity as the score")
def _cosine_sim_score(bdd_state: dict) -> None:
    score = _s(bdd_state)["score"]
    assert isinstance(score, float) and 0.0 <= score <= 1.0


@then("the sentence-transformers model is loaded only on first use")
def _loaded_once(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    model_a = emb._get_model()
    model_b = emb._get_model()
    assert model_a is model_b, "model instance changed between calls"


@then("the same model instance is reused for all subsequent calls")
def _model_reused(bdd_state: dict) -> None:
    emb = _s(bdd_state)["embedding"]
    assert emb._model is not None
    model_ref = emb._model
    emb("another query", "another text")
    assert emb._model is model_ref, "model was replaced on subsequent call"
