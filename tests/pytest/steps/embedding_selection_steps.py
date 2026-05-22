"""Step definitions for the embedding-selection scenarios in
docs/features/algorithms/embedding-interface.feature.

These scenarios exercise the TOOL_SELECTOR_EMBEDDING environment variable
that drives which Embedding the MCP server picks at startup.

The shared "When the server starts" step is registered in
``corpus_configuration_steps.py`` and now also constructs a
``ToolSelectorServer`` via ``build_server()``, stashing it under
``bdd_state["corpus_cfg"]["server"]`` (or the raised exception under
``["error"]``) so these steps can inspect the result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then

from tool_selector_mcp.embeddings import (
    AllMiniLML6V2Embedding,
    AnthropicEmbedding,
    TokenOverlapEmbedding,
    UnknownEmbeddingError,
)


def _s(bdd_state: dict) -> dict:
    return bdd_state.setdefault("corpus_cfg", {})


def _ensure_minimal_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write a valid corpus file in tmp_path so build_server() reaches the embedding step."""
    path = tmp_path / ".mcp-corpus.json"
    path.write_text(json.dumps({"mcpServers": {"echo-mcp": {"command": "echo"}}}))
    monkeypatch.chdir(tmp_path)


# --- Given --------------------------------------------------------------


@given(parsers.parse('the environment variable TOOL_SELECTOR_EMBEDDING is set to "{value}"'))
def _set_emb_env(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TOOL_SELECTOR_EMBEDDING", value)
    _ensure_minimal_corpus(tmp_path, monkeypatch)


@given("the environment variable TOOL_SELECTOR_EMBEDDING is not set")
def _unset_emb_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TOOL_SELECTOR_EMBEDDING", raising=False)
    _ensure_minimal_corpus(tmp_path, monkeypatch)


# --- Then ---------------------------------------------------------------


_EXPECTED: dict[str, type] = {
    "token-overlap": TokenOverlapEmbedding,
    "Anthropic": AnthropicEmbedding,
    "All-MiniLM-L6-v2": AllMiniLML6V2Embedding,
}


@then(parsers.parse("retrieval uses the {name} embedding"))
def _retrieval_uses(name: str, bdd_state: dict) -> None:
    state = _s(bdd_state)
    server = state.get("server")
    assert server is not None, f"server failed to start: {state.get('error')!r}"
    expected_cls = _EXPECTED[name]
    assert isinstance(server.embedding, expected_cls), (
        f"expected {expected_cls.__name__}, got {type(server.embedding).__name__}"
    )


@then("the server exits with an error indicating the embedding name is unknown")
def _unknown_emb_error(bdd_state: dict) -> None:
    err = _s(bdd_state).get("error")
    assert isinstance(err, UnknownEmbeddingError), f"got {err!r}"
