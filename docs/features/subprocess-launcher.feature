Feature: Subprocess Launcher
  make_subprocess_launcher returns an AsyncLauncher that spawns the downstream agent
  as an MCP stdio subprocess, forwards the tool call, and returns the result.

  Scenario: launcher assembles subprocess parameters from the agent corpus entry
    Given a subprocess launcher agent with command "npx" and args ["-y", "@mcp/server-github"]
    And the MCP client is mocked
    When the subprocess launcher is called with tool "create_issue" and arguments {"title": "test"}
    Then stdio_client received command "npx" and args ["-y", "@mcp/server-github"]

  Scenario: launcher forwards the tool call to the MCP session
    Given a subprocess launcher agent with command "npx" and args ["-y", "@mcp/server-github"]
    And the MCP client is mocked
    When the subprocess launcher is called with tool "create_issue" and arguments {"title": "test"}
    Then session.call_tool was called with "create_issue" and {"title": "test"}

  Scenario: launcher returns the result from the MCP session
    Given a subprocess launcher agent with command "npx" and args ["-y", "@mcp/server-github"]
    And the MCP client is mocked to return {"content": "created"}
    When the subprocess launcher is called with tool "create_issue" and arguments {}
    Then the subprocess launcher returns {"content": "created"}
