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
)

scenarios("installation.feature")
scenarios("mcp-server.feature")
scenarios("corpus-configuration.feature")
scenarios("server-tools.feature")
scenarios("tool-to-agent-retrieval-algorithm.feature")
