"""Unit tests for code paths not covered by the BDD scenario suite."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tool_selector_mcp.corpus import Agent, Corpus, Tool, load_corpus
from tool_selector_mcp.embeddings import ScriptedEmbedding
from tool_selector_mcp.retrieval import _score, search, search_with_info
from tool_selector_mcp.server import (
    ToolSelectorServer,
    UnknownToolError,
    _parse_tool_id,
    make_launcher,
    make_recording_async_launcher,
    make_recording_launcher,
    make_subprocess_launcher,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _corpus() -> Corpus:
    return Corpus(
        agents={
            "github-mcp": Agent(
                agent_id="github-mcp",
                description="GitHub agent",
                command="npx",
                args=(),
                env={},
                url=None,
                transport="stdio",
                headers={},
                tools=(
                    Tool(
                        name="create_issue",
                        description="Create a GitHub issue",
                        input_schema={},
                    ),
                ),
            )
        }
    )


# ---------------------------------------------------------------------------
# corpus – load_corpus with explicit host_env (corpus.py branch 110->112)
# ---------------------------------------------------------------------------


def test_load_corpus_with_explicit_host_env(tmp_path: Path) -> None:
    # Exercises the host_env-is-not-None branch (line 110 → 112, skipping 111).
    corpus_file = tmp_path / "corpus.json"
    corpus_file.write_text(
        json.dumps({"mcpServers": {"my-agent": {"command": "echo", "description": "test"}}})
    )
    corpus = load_corpus(corpus_file, host_env={})
    assert "my-agent" in corpus.agents


# ---------------------------------------------------------------------------
# embeddings – ScriptedEmbedding.call_count and .called_texts
# ---------------------------------------------------------------------------


def test_scripted_call_count():
    emb = ScriptedEmbedding(scores={"text1": 0.8}, default=0.2)
    assert emb.call_count == 0
    emb("q1", "text1")
    emb("q2", "other")
    assert emb.call_count == 2


def test_scripted_called_texts():
    emb = ScriptedEmbedding(scores={"text1": 0.8})
    emb("q1", "text1")
    emb("q2", "other")
    assert emb.called_texts == ["text1", "other"]


# ---------------------------------------------------------------------------
# embeddings – AnthropicEmbedding lazy client creation (lines 76-78)
# ---------------------------------------------------------------------------


def test_anthropic_get_client_creates_lazily():
    mock_anthropic = MagicMock()
    mock_client_instance = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client_instance

    from tool_selector_mcp.embeddings import AnthropicEmbedding

    with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
        emb = AnthropicEmbedding(api_key="test-key")
        assert emb._client is None
        client = emb._get_client()
        assert client is mock_client_instance
        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")


# ---------------------------------------------------------------------------
# embeddings – AllMiniLML6V2Embedding lazy model creation (lines 113-115)
# ---------------------------------------------------------------------------


def test_minilm_get_model_creates_lazily():
    mock_st = MagicMock()
    mock_model_instance = MagicMock()
    mock_st.SentenceTransformer.return_value = mock_model_instance

    from tool_selector_mcp.embeddings import AllMiniLML6V2Embedding

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        emb = AllMiniLML6V2Embedding()
        assert emb._model is None
        model = emb._get_model()
        assert model is mock_model_instance
        mock_st.SentenceTransformer.assert_called_once_with("all-MiniLM-L6-v2")


# ---------------------------------------------------------------------------
# retrieval – _score edge cases (line 110)
# ---------------------------------------------------------------------------


def test_score_empty_query_keywords_returns_zero():
    assert _score(set(), "some text") == 0.0


def test_score_empty_target_returns_zero():
    assert _score({"keyword"}, "") == 0.0


# ---------------------------------------------------------------------------
# retrieval – search_with_info rewrite=False branch (line 146->150)
# ---------------------------------------------------------------------------


def test_search_with_info_no_rewrite():
    corpus = _corpus()
    info = search_with_info(corpus, "create issue", rewrite=False)
    assert info.total_catalog_size > 0


# ---------------------------------------------------------------------------
# retrieval – search() with embedding delegates to search_with_info (line 219)
# ---------------------------------------------------------------------------


def test_search_with_custom_embedding():
    corpus = _corpus()
    emb = ScriptedEmbedding(default=0.5)
    results = search(corpus, "create issue", embedding=emb)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# server – _parse_tool_id error cases (lines 73, 77, 81)
# ---------------------------------------------------------------------------


def test_parse_tool_id_unknown_agent_raises():
    corpus = _corpus()
    with pytest.raises(UnknownToolError):
        _parse_tool_id(corpus, "nonexistent-agent.create_issue")


def test_parse_tool_id_unknown_tool_in_agent_raises():
    corpus = _corpus()
    with pytest.raises(UnknownToolError):
        _parse_tool_id(corpus, "github-mcp.nonexistent_tool")


def test_parse_tool_id_no_dot_success():
    corpus = _corpus()
    agent, tool = _parse_tool_id(corpus, "create_issue")
    assert agent.agent_id == "github-mcp"
    assert tool.name == "create_issue"


# ---------------------------------------------------------------------------
# server – invoke_tool with server= error cases (lines 157, 160, 168)
# ---------------------------------------------------------------------------


def test_invoke_tool_unknown_server_raises():
    corpus = _corpus()
    _, launcher = make_recording_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    with pytest.raises(UnknownToolError):
        server.invoke_tool("create_issue", server="nonexistent-server")


def test_invoke_tool_unknown_tool_in_server_raises():
    corpus = _corpus()
    _, launcher = make_recording_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    with pytest.raises(UnknownToolError):
        server.invoke_tool("nonexistent_tool", server="github-mcp")


def test_invoke_tool_no_launcher_raises():
    corpus = _corpus()
    server = ToolSelectorServer(corpus)
    with pytest.raises(RuntimeError, match="no launcher configured"):
        server.invoke_tool("create_issue")


# ---------------------------------------------------------------------------
# server – invoke_tool_async with server= path (lines 181-186)
# ---------------------------------------------------------------------------


def test_invoke_tool_async_with_server_success():
    corpus = _corpus()
    calls, launcher = make_recording_async_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    result = asyncio.run(server.invoke_tool_async("create_issue", {}, server="github-mcp"))
    assert result["ok"] is True
    assert calls[0].agent_id == "github-mcp"
    assert calls[0].tool_name == "create_issue"


def test_invoke_tool_async_unknown_server_raises():
    corpus = _corpus()
    _, launcher = make_recording_async_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    with pytest.raises(UnknownToolError):
        asyncio.run(server.invoke_tool_async("create_issue", server="nonexistent-server"))


def test_invoke_tool_async_unknown_tool_in_server_raises():
    corpus = _corpus()
    _, launcher = make_recording_async_launcher()
    server = ToolSelectorServer(corpus, launcher=launcher)
    with pytest.raises(UnknownToolError):
        asyncio.run(server.invoke_tool_async("nonexistent_tool", server="github-mcp"))


# ---------------------------------------------------------------------------
# cli – main() error paths (lines 33-37)
# ---------------------------------------------------------------------------


def test_main_returns_1_on_corpus_error():
    from tool_selector_mcp.cli import main
    from tool_selector_mcp.corpus import CorpusError

    with patch("tool_selector_mcp.cli.build_server", side_effect=CorpusError("bad corpus")):
        assert main() == 1


def test_main_returns_1_on_unknown_embedding_error():
    from tool_selector_mcp.cli import main
    from tool_selector_mcp.embeddings import UnknownEmbeddingError

    with patch("tool_selector_mcp.cli.build_server", side_effect=UnknownEmbeddingError("bad-emb")):
        assert main() == 1


# ---------------------------------------------------------------------------
# cli – main() success path: inner tool functions (lines 38-67)
# ---------------------------------------------------------------------------


def test_main_success_path_and_tool_functions():
    from tool_selector_mcp.cli import main

    mock_server = MagicMock()
    mock_server.search_tools.return_value = []
    mock_server.get_tool_details.return_value = []
    mock_server.invoke_tool_async = AsyncMock(return_value="ok")

    captured: dict = {}

    def capture_tool():
        def decorator(func):
            captured[func.__name__] = func
            return func

        return decorator

    mock_app = MagicMock()
    mock_app.tool.side_effect = capture_tool

    with patch("tool_selector_mcp.cli.build_server", return_value=mock_server):
        with patch("tool_selector_mcp.cli.FastMCP", return_value=mock_app):
            result = main()

    assert result == 0
    mock_app.run.assert_called_once()

    # Exercise search_tools inner function
    search_result = captured["search_tools"]("query", 2)
    assert search_result == []

    # Exercise get_tool_details inner function – success path
    detail_result = captured["get_tool_details"](["tool1"])
    assert detail_result == []

    # Exercise get_tool_details inner function – UnknownToolError path
    mock_server.get_tool_details.side_effect = UnknownToolError("tool1")
    error_result = captured["get_tool_details"](["tool1"])
    assert error_result == [{"error": "tool not found in corpus: tool1"}]

    # Exercise invoke_tool inner function – success path
    ok_result = asyncio.run(captured["invoke_tool"]("tool", {}, None))
    assert ok_result == {"result": "ok"}

    # Exercise invoke_tool inner function – error path
    mock_server.invoke_tool_async = AsyncMock(side_effect=RuntimeError("boom"))
    err_result = asyncio.run(captured["invoke_tool"]("tool", {}, None))
    assert err_result == {"error": "boom"}


# ---------------------------------------------------------------------------
# make_launcher – helpers
# ---------------------------------------------------------------------------


def _agent_stdio(command: str = "npx") -> Agent:
    return Agent(
        agent_id="test-agent",
        description="test",
        command=command,
        args=(),
        env={},
        url=None,
        transport="stdio",
        headers={},
        tools=(),
    )


def _agent_sse(url: str = "https://example.com/mcp") -> Agent:
    return Agent(
        agent_id="sse-agent",
        description="test",
        command=None,
        args=(),
        env={},
        url=url,
        transport="sse",
        headers={"Authorization": "Bearer tok"},
        tools=(),
    )


def _agent_streamable_http(url: str = "https://example.com/mcp") -> Agent:
    return Agent(
        agent_id="http-agent",
        description="test",
        command=None,
        args=(),
        env={},
        url=url,
        transport="streamable-http",
        headers={},
        tools=(),
    )


def _build_mock_stdio() -> dict:
    mock_read, mock_write = MagicMock(), MagicMock()
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value={"ok": True})
    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)
    return {
        "mock_client": MagicMock(return_value=mock_stdio_cm),
        "MockSession": MagicMock(return_value=mock_session_cm),
        "mock_session": mock_session,
    }


def _build_mock_remote(n_yield: int = 2) -> dict:
    mock_read, mock_write = MagicMock(), MagicMock()
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value={"ok": True})
    mock_remote_cm = AsyncMock()
    if n_yield == 3:
        mock_remote_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write, MagicMock()))
    else:
        mock_remote_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    mock_remote_cm.__aexit__ = AsyncMock(return_value=None)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=None)
    return {
        "mock_client": MagicMock(return_value=mock_remote_cm),
        "MockSession": MagicMock(return_value=mock_session_cm),
        "mock_session": mock_session,
    }


# ---------------------------------------------------------------------------
# make_launcher – stdio transport
# ---------------------------------------------------------------------------


def test_make_launcher_stdio_calls_tool():
    m = _build_mock_stdio()
    with (
        patch("mcp.client.stdio.stdio_client", m["mock_client"]),
        patch("mcp.ClientSession", m["MockSession"]),
        patch("mcp.StdioServerParameters", MagicMock(return_value=MagicMock())),
    ):
        result = asyncio.run(make_launcher()(_agent_stdio(), "create_issue", {"repo": "x"}))
    assert result == {"ok": True}
    m["mock_session"].call_tool.assert_called_once_with("create_issue", {"repo": "x"})


def test_make_launcher_stdio_no_command_raises():
    agent = _agent_stdio()
    agent = Agent(
        agent_id=agent.agent_id,
        description=agent.description,
        command=None,
        args=agent.args,
        env=agent.env,
        url=agent.url,
        transport="stdio",
        headers=agent.headers,
        tools=agent.tools,
    )
    with pytest.raises(RuntimeError, match="has no command"):
        asyncio.run(make_launcher()(agent, "create_issue", {}))


# ---------------------------------------------------------------------------
# make_launcher – SSE transport
# ---------------------------------------------------------------------------


def test_make_launcher_sse_calls_tool():
    m = _build_mock_remote(n_yield=2)
    with (
        patch("mcp.client.sse.sse_client", m["mock_client"]),
        patch("mcp.ClientSession", m["MockSession"]),
    ):
        result = asyncio.run(make_launcher()(_agent_sse(), "search", {"q": "hello"}))
    assert result == {"ok": True}
    m["mock_session"].call_tool.assert_called_once_with("search", {"q": "hello"})


def test_make_launcher_sse_no_url_raises():
    agent = Agent(
        agent_id="sse-agent",
        description="test",
        command=None,
        args=(),
        env={},
        url=None,
        transport="sse",
        headers={},
        tools=(),
    )
    with pytest.raises(RuntimeError, match="has no url"):
        asyncio.run(make_launcher()(agent, "search", {}))


# ---------------------------------------------------------------------------
# make_launcher – streamable-http transport
# ---------------------------------------------------------------------------


def test_make_launcher_streamable_http_calls_tool():
    m = _build_mock_remote(n_yield=3)
    with (
        patch("mcp.client.streamable_http.streamablehttp_client", m["mock_client"]),
        patch("mcp.ClientSession", m["MockSession"]),
    ):
        result = asyncio.run(make_launcher()(_agent_streamable_http(), "read_doc", {}))
    assert result == {"ok": True}
    m["mock_session"].call_tool.assert_called_once_with("read_doc", {})


def test_make_launcher_streamable_http_no_url_raises():
    agent = Agent(
        agent_id="http-agent",
        description="test",
        command=None,
        args=(),
        env={},
        url=None,
        transport="streamable-http",
        headers={},
        tools=(),
    )
    with pytest.raises(RuntimeError, match="has no url"):
        asyncio.run(make_launcher()(agent, "read_doc", {}))


# ---------------------------------------------------------------------------
# make_launcher – unknown transport
# ---------------------------------------------------------------------------


def test_make_launcher_unknown_transport_raises():
    agent = Agent(
        agent_id="bad-agent",
        description="test",
        command=None,
        args=(),
        env={},
        url="https://example.com",
        transport="grpc",
        headers={},
        tools=(),
    )
    with pytest.raises(ValueError, match="unknown transport"):
        asyncio.run(make_launcher()(agent, "tool", {}))


# ---------------------------------------------------------------------------
# corpus – transport auto-detection
# ---------------------------------------------------------------------------


def test_load_corpus_auto_detects_stdio_transport(tmp_path: Path) -> None:
    corpus_file = tmp_path / "corpus.json"
    corpus_file.write_text(
        json.dumps(
            {"mcpServers": {"my-agent": {"command": "npx", "description": "test", "tools": []}}}
        )
    )
    corpus = load_corpus(corpus_file, host_env={})
    assert corpus.agents["my-agent"].transport == "stdio"


def test_load_corpus_auto_detects_sse_transport(tmp_path: Path) -> None:
    corpus_file = tmp_path / "corpus.json"
    corpus_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "remote-agent": {
                        "url": "https://example.com/mcp",
                        "description": "test",
                        "tools": [],
                    }
                }
            }
        )
    )
    corpus = load_corpus(corpus_file, host_env={})
    assert corpus.agents["remote-agent"].transport == "sse"
    assert corpus.agents["remote-agent"].url == "https://example.com/mcp"


# ---------------------------------------------------------------------------
# make_subprocess_launcher – null command guard (line 214)
# ---------------------------------------------------------------------------


def test_make_subprocess_launcher_no_command_raises():
    agent = Agent(
        agent_id="no-cmd",
        description="test",
        command=None,
        args=(),
        env={},
        url=None,
        transport="stdio",
        headers={},
        tools=(),
    )
    with pytest.raises(RuntimeError, match="has no command"):
        asyncio.run(make_subprocess_launcher()(agent, "tool", {}))
