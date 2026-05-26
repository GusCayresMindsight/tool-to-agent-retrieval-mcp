Feature: Installation
  tool-to-agent-retrieval-mcp is distributed as a Python package on PyPI and launched via
  uv's one-shot launcher uvx, so no virtualenv or persistent install is required.

  Background:
    Given uv (which provides the uvx launcher) is installed on the host system
    And the uvx executable is on the PATH

  Scenario: Starting the server via uvx
    Given the tool-to-agent-retrieval-mcp package is available on PyPI
    When a client runs "uvx tool-to-agent-retrieval-mcp"
    Then the MCP server starts and listens for connections

  Scenario: Configuring the server in Claude Desktop
    Given a claude_desktop_config.json file
    When the following entry is added to "mcpServers":
      """
      "tool-to-agent-retrieval-mcp": {
        "command": "uvx",
        "args": ["tool-to-agent-retrieval-mcp"]
      }
      """
    Then Claude Desktop starts the server automatically on launch
    And the tool-selector tools become available in the session

  Scenario: Configuring the server in Claude Code
    Given a .claude/settings.json file
    When the following entry is added to "mcpServers":
      """
      "tool-to-agent-retrieval-mcp": {
        "command": "uvx",
        "args": ["tool-to-agent-retrieval-mcp"]
      }
      """
    Then Claude Code starts the server automatically on launch
    And the tool-selector tools become available in the session
