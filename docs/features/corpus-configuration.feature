Feature: Corpus Configuration
  The server loads its tool-agent catalog from a JSON corpus file at startup.
  The file path defaults to .mcp-corpus.json in the working directory where
  npx is run, and can be overridden with the MCP_CORPUS_PATH environment variable.
  Corpus env values may reference host environment variables using ${VAR_NAME}
  syntax so secrets stay out of the file.

  Scenario: Server loads corpus from the default file path
    Given a file ".mcp-corpus.json" exists in the current working directory
    When the server starts via "npx tool-selector-mcp"
    Then the catalog is populated from ".mcp-corpus.json"

  Scenario: Server loads corpus from a custom path set via environment variable
    Given a corpus file exists at "/custom/path/corpus.json"
    And the environment variable MCP_CORPUS_PATH is set to "/custom/path/corpus.json"
    When the server starts
    Then the catalog is populated from "/custom/path/corpus.json"

  Scenario: MCP_CORPUS_PATH takes precedence over the default path
    Given a file ".mcp-corpus.json" exists in the current working directory
    And a corpus file exists at "/custom/path/corpus.json"
    And the environment variable MCP_CORPUS_PATH is set to "/custom/path/corpus.json"
    When the server starts
    Then the catalog is populated from "/custom/path/corpus.json"
    And ".mcp-corpus.json" is not read

  Scenario: Server fails to start when the corpus file is not found
    Given no corpus file exists at the configured path
    When the server starts
    Then the server exits with an error indicating the corpus file was not found

  Scenario: Corpus file structure extends .mcp.json with descriptions and tools
    Given a ".mcp-corpus.json" file with the following content:
      """
      {
        "mcpServers": {
          "github-mcp": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": { "GITHUB_TOKEN": "<token>" },
            "description": "Interact with GitHub repositories, issues, and PRs",
            "tools": [
              {
                "name": "create_pull_request",
                "description": "Open a new pull request on a GitHub repository"
              },
              {
                "name": "list_issues",
                "description": "List open issues for a repository"
              }
            ]
          },
          "slack-mcp": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-slack"],
            "description": "Send messages and manage Slack workspaces",
            "tools": [
              {
                "name": "send_message",
                "description": "Send a message to a Slack channel"
              }
            ]
          }
        }
      }
      """
    When the server starts
    Then the catalog contains the agent "github-mcp" with 2 tools
    And the catalog contains the agent "slack-mcp" with 1 tool

  Scenario: Corpus env values are resolved from host environment variables
    Given a ".mcp-corpus.json" file with the following content:
      """
      {
        "mcpServers": {
          "github-mcp": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" },
            "description": "Interact with GitHub repositories, issues, and PRs",
            "tools": []
          }
        }
      }
      """
    And the host environment variable GITHUB_TOKEN is set to "ghp_secret"
    When the server launches "github-mcp" to handle a tool call
    Then the agent is started with GITHUB_TOKEN="ghp_secret"

  Scenario: Server fails to start when a referenced env variable is unset
    Given a corpus entry with env { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    And the host environment variable GITHUB_TOKEN is not set
    When the server starts
    Then the server exits with an error indicating GITHUB_TOKEN is unresolved

  Scenario: Server executes the selected agent's tool
    Given the corpus contains "github-mcp" with command "npx", args ["-y", "@modelcontextprotocol/server-github"], and env GITHUB_TOKEN
    When a client invokes a tool that resolves to "github-mcp"
    Then the server launches "github-mcp" with its command, args, and resolved env
    And the server returns the result of the tool call to the client
