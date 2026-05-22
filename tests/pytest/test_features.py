"""All BDD scenarios for tool-selector-mcp.

Each `scenarios()` call binds every scenario from the named feature file
in docs/features/. Step implementations live in the sibling `steps/`
package — importing each module here registers its @given/@when/@then
decorators with pytest-bdd before scenarios are collected.
"""

from pytest_bdd import scenarios

from steps import (  # noqa: F401
    installation_steps,
    mcp_server_steps,
    corpus_configuration_steps,
    server_tools_steps,
    tool_to_agent_retrieval_steps,
    corpus_embedding_steps,
    embedding_interface_steps,
    retrieval_loop_steps,
    scripted_embedding_steps,
    anthropic_embedding_steps,
    minilm_embedding_steps,
)

scenarios("installation.feature")
scenarios("mcp-server.feature")
scenarios("corpus-configuration.feature")
scenarios("server-tools.feature")
scenarios("tool-retrieval.feature")
scenarios("algorithms/corpus-embedding.feature")
scenarios("algorithms/embedding-interface.feature")
scenarios("algorithms/tool-to-agent-retrieval-loop.feature")
scenarios("algorithms/embeddings/scripted.feature")
scenarios("algorithms/embeddings/anthropic.feature")
scenarios("algorithms/embeddings/all-minilm-l6-v2.feature")
