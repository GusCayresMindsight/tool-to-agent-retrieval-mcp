Feature: Tool-to-Agent Retrieval Algorithm
  The tool-selector-mcp uses a unified Tool-to-Agent Retrieval algorithm based on
  "Tool-to-Agent Retrieval: Bridging Tools and Agents for Scalable LLM Multi-Agent Systems"
  (Lumer et al., PricewaterhouseCoopers, arXiv:2511.01854v2, Nov 2025).

  The system models agents and tools as a bipartite graph G = (A, T, E) where
  ownership edges link each tool to its parent agent. Both are embedded in a shared
  vector space and indexed in a unified catalog C = CT ∪ CA. A two-stage retrieval
  pipeline first rewrites the user query into focused keywords using an LLM, then
  performs vector similarity search over C.

  Background:
    Given a catalog containing the following agents:
      | agent_id     | name         | description                                        |
      | github-mcp   | GitHub MCP   | Interact with GitHub repositories, issues, and PRs |
      | postgres-mcp | Postgres MCP | Execute queries and manage PostgreSQL databases    |
      | slack-mcp    | Slack MCP    | Send messages and manage Slack workspaces          |
    And the catalog contains the following tools:
      | tool_id             | description                                     | owner        |
      | create_pull_request | Open a new pull request on a GitHub repository  | github-mcp   |
      | list_issues         | List open issues for a repository               | github-mcp   |
      | run_query           | Execute a SQL query on a PostgreSQL database    | postgres-mcp |
      | send_message        | Send a message to a Slack channel               | slack-mcp    |

  Scenario: Direct query returns top-K agents ranked by relevance
    When the query "open a pull request for the bug fix" is submitted directly with K=1
    Then the top result is the agent "github-mcp"

  Scenario: Query matching a tool description returns the tool's parent agent
    When the query "open a pull request" is submitted with K=1
    Then "github-mcp" is returned in the results

  Scenario: Query matching an agent description returns that agent
    When the query "interact with GitHub repositories" is submitted with K=1
    Then "github-mcp" is returned in the results

  Scenario: Multiple top-ranked entries under the same agent produce only one result entry
    When the query "manage GitHub issues and pull requests" is submitted with K=5
    Then "github-mcp" appears exactly once in the results

  Scenario: Step-wise querying retrieves independent agents per sub-task
    Given the multi-step query "list open GitHub issues, then send a Slack summary"
    When the query is decomposed into sub-tasks:
      | step | sub_query                         |
      | 1    | list open GitHub issues           |
      | 2    | send a message to a Slack channel |
    And each sub-query is submitted independently to the retrieval algorithm
    Then step 1 returns "github-mcp" as the top agent
    And step 2 returns "slack-mcp" as the top agent
    And the combined result covers both required agents

  Scenario: Unified catalog surfaces a match that an agent-only index would miss
    Given an additional agent "collab-mcp" described as "code collaboration platform"
    And "collab-mcp" has a tool "create_pr" described as "Open a new pull request on a GitHub repository"
    When the query "open a pull request" is submitted with K=3
    Then "collab-mcp" is returned in the results

  Scenario: Two-stage retrieval rewrites the query before embedding search
    Given the user query is "hey can you go ahead and open up a pull request for me on the bug fix branch"
    When the retrieval pipeline runs stage 1 (LLM query rewrite)
    Then the query is condensed to keywords focused on the action and target, e.g. "open pull request bug fix"
    And the condensed query is passed to stage 2 (embedding similarity search)
    And the top result is the agent "github-mcp"

  Scenario: Two-stage retrieval can be bypassed when query rewriting is disabled
    Given query rewriting is disabled
    When the query "open a pull request" is submitted with K=1
    Then the embedding search runs directly on the raw query
    And "github-mcp" is returned in the results
