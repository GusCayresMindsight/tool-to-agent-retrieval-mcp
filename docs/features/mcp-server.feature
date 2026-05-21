Feature: MCP Server
  tool-selector-mcp is an MCP server that acts as a routing layer for multi-agent systems.
  Given a natural language query, it identifies which MCP agents are best suited to fulfill it.
  It does not execute tools itself — its sole responsibility is retrieval.

  Scenario: Starting the server via npx
    Given the tool-selector-mcp package is available on npm
    When a client runs "npx -y tool-selector-mcp"
    Then the MCP server starts and listens for connections

  Scenario: Configuring the server in Claude Desktop
    Given a claude_desktop_config.json file
    When the following entry is added to "mcpServers":
      """
      "tool-selector": {
        "command": "npx",
        "args": ["-y", "tool-selector-mcp"]
      }
      """
    Then Claude Desktop starts the server automatically on launch
    And the tool-selector tools become available in the session

  Scenario: Configuring the server in Claude Code
    Given a .claude/settings.json file
    When the following entry is added to "mcpServers":
      """
      "tool-selector": {
        "command": "npx",
        "args": ["-y", "tool-selector-mcp"]
      }
      """
    Then Claude Code starts the server automatically on launch
    And the tool-selector tools become available in the session

  Scenario: Server acts as routing layer, not executor
    Given the server is running
    And downstream agents "github-mcp" and "postgres-mcp" are registered
    When a client queries the server for the best agent to handle a task
    Then the server returns a ranked list of agents
    But the server does not invoke any tool on the downstream agents

  Scenario: Server does not orchestrate multi-step workflows
    Given the server is running
    When a client submits a multi-step query
    Then the server returns relevant agents for each step
    But the server does not sequence or coordinate the steps
