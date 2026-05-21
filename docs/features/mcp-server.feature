Feature: MCP Server
  tool-selector-mcp is an MCP server designed to be the sole MCP server registered
  in a client (Claude Desktop, Claude Code, etc.). All downstream agents live in the
  corpus file rather than being registered directly. Given a natural language query,
  it identifies the best-suited downstream agent, invokes the requested tool on that
  agent, and returns the result to the client.

  Scenario: tool-selector-mcp is the only registered MCP server
    Given a client configured with only "tool-selector-mcp" in its mcpServers
    And downstream agents "github-mcp" and "slack-mcp" are defined in the corpus file
    Then "github-mcp" and "slack-mcp" are not registered directly in the client
    And they are only reachable through tool-selector-mcp

  Scenario: Server executes the selected tool on the chosen downstream agent
    Given the server is running
    And the corpus contains agents with their command, args, and env
    When a client invokes a tool through tool-selector-mcp
    Then the server starts the chosen downstream agent using its command, args, and env
    And the server forwards the tool call to that agent
    And the server returns the downstream agent's result to the client

  Scenario: Server does not orchestrate multi-step workflows
    Given the server is running
    When a client submits a multi-step query
    Then the server returns relevant agents for each step
    But the server does not sequence or coordinate the steps
