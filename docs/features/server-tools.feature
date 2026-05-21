Feature: Server Tools
  tool-selector-mcp exposes three MCP tools. search_tools takes a natural language
  query and returns the best-matching agents from the corpus, ranked by relevance,
  with lightweight metadata only. get_tool_details returns the full input schemas
  for a specified set of tools so clients fetch heavy schemas only after selection.
  invoke_tool accepts a server and tool name in the same style a model would use
  to call a downstream MCP tool directly; the server starts the owning agent,
  forwards the call, and returns the agent's result.

  Scenario: search_tools returns the top-ranked agent for a query
    Given the server is running with a corpus containing "github-mcp", "postgres-mcp", and "slack-mcp"
    When search_tools is called with query "open a pull request" and K=1
    Then the result contains 1 agent
    And "github-mcp" is the top result

  Scenario: search_tools K parameter controls the number of results
    Given the server is running with a corpus containing "github-mcp", "postgres-mcp", and "slack-mcp"
    When search_tools is called with query "manage data" and K=2
    Then the result contains at most 2 agents

  Scenario: search_tools defaults to K=1 when K is not specified
    Given the server is running with a corpus containing "github-mcp", "postgres-mcp", and "slack-mcp"
    When search_tools is called with query "open a pull request" without specifying K
    Then the result contains exactly 1 agent

  Scenario: search_tools returns lightweight metadata, not full schemas
    Given the corpus contains "github-mcp" with tool "create_pull_request" having a large input schema
    When search_tools is called with query "open a pull request" and K=1
    Then each result includes the agent id, tool name, and a short description
    But the result does not include the tool's full input schema

  Scenario: get_tool_details returns full schemas for the requested tools
    Given the corpus contains "github-mcp" with tools "create_pull_request" and "list_issues"
    When get_tool_details is called with ["github-mcp.create_pull_request", "github-mcp.list_issues"]
    Then the result contains the full input schema for each requested tool

  Scenario: get_tool_details returns an error for unknown tools
    Given the corpus does not contain a tool named "unknown_tool"
    When get_tool_details is called with ["unknown_tool"]
    Then the server returns an error indicating the tool was not found

  Scenario: invoke_tool resolves a known tool to its parent agent and executes it
    Given the corpus contains agent "github-mcp" with tool "create_pull_request"
    When invoke_tool is called with server "github-mcp", tool "create_pull_request", and arguments {"repo": "my-repo", "title": "Fix bug"}
    Then the server starts "github-mcp" using its command, args, and resolved env
    And the server forwards the call to "create_pull_request" on that agent
    And the server returns the agent's response to the client

  Scenario: invoke_tool identifies the owning agent from tool name alone
    Given the corpus contains tool "create_pull_request" owned by "github-mcp"
    When invoke_tool is called with tool "create_pull_request" and arguments {"repo": "my-repo", "title": "Fix bug"}
    Then the server identifies "github-mcp" as the target agent
    And the server forwards the call and returns the result

  Scenario: invoke_tool returns an error when the tool is not in the corpus
    Given the corpus does not contain a tool named "unknown_tool"
    When invoke_tool is called with tool "unknown_tool" and arguments {}
    Then the server returns an error indicating the tool was not found
