"""Step definitions for docs/features/algorithms/embeddings/anthropic.feature.

Shared When/Then steps are defined in embedding_interface_steps.py.
All embedding modules share bdd_state["emb_test"] as the state key.

The `anthropic` package is mocked via sys.modules so these tests run without
requiring the SDK to be installed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pytest_bdd import given, then


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("emb_test", {})


def _make_mock_client(score: float = 0.85) -> MagicMock:
    content = MagicMock()
    content.text = str(score)
    message = MagicMock()
    message.content = [content]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


def _make_embedding(mock_client: MagicMock):
    """Instantiate AnthropicEmbedding with the anthropic SDK mocked out."""
    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = mock_client

    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        from tool_selector_mcp.embeddings import AnthropicEmbedding
        emb = AnthropicEmbedding(api_key="test-key")
    # Ensure the mock client is wired up regardless of caching
    emb._client = mock_client
    return emb


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("an Anthropic embedding configured with a valid API key")
def _anthropic_with_key(bdd_state: dict) -> None:
    mock_client = _make_mock_client(0.85)
    _s(bdd_state)["embedding"] = _make_embedding(mock_client)
    _s(bdd_state)["mock_client"] = mock_client


@given("an Anthropic embedding instantiated once")
def _anthropic_single_instance(bdd_state: dict) -> None:
    mock_client = _make_mock_client(0.75)
    _s(bdd_state)["embedding"] = _make_embedding(mock_client)
    _s(bdd_state)["mock_client"] = mock_client


@given("an Anthropic embedding")
def _anthropic_bare(bdd_state: dict) -> None:
    mock_client = _make_mock_client(0.6)
    _s(bdd_state)["embedding"] = _make_embedding(mock_client)
    _s(bdd_state)["mock_client"] = mock_client


# ---------------------------------------------------------------------------
# Then – Anthropic-specific assertions
# ---------------------------------------------------------------------------


@then("it issues a request to the Anthropic messages API")
def _issued_request(bdd_state: dict) -> None:
    mock_client = _s(bdd_state)["mock_client"]
    assert mock_client.messages.create.called, "messages.create was not called"


@then("returns the float score extracted from the response")
def _returns_float_from_response(bdd_state: dict) -> None:
    score = _s(bdd_state)["score"]
    assert isinstance(score, float) and 0.0 <= score <= 1.0


@then("the same Anthropic client is used for every call")
def _same_client_reused(bdd_state: dict) -> None:
    mock_client = _s(bdd_state)["mock_client"]
    assert mock_client.messages.create.call_count == 3, (
        f"expected 3 API calls, got {mock_client.messages.create.call_count}"
    )
