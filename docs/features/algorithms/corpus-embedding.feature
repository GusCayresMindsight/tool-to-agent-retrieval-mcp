Feature: Corpus Embedding – Offline Index Construction
  Algorithm 1 (Lumer et al., arXiv:2511.01854v2) requires a unified catalog C that is
  assembled offline from the bipartite graph G = (A, T, E) before any query is processed.

  C = CT ∪ CA, where:
    CT  – tool corpus: tool names and descriptions, each carrying own(t) → parent agent
    CA  – agent corpus: agent names and descriptions as top-level nodes

  The type function τ(·) ∈ {agent, tool} and owner map own(·) are established at
  index-build time and consumed by the retrieval loop at query time.

  Background:
    Given a catalog containing the following agents:
      | agent_id     | description                                        |
      | github-mcp   | Interact with GitHub repositories, issues, and PRs |
      | postgres-mcp | Execute queries and manage PostgreSQL databases    |
    And the catalog contains the following tools:
      | tool_id             | description                                    | owner        |
      | create_pull_request | Open a new pull request on a GitHub repository | github-mcp   |
      | list_issues         | List open issues for a repository              | github-mcp   |
      | run_query           | Execute a SQL query on a PostgreSQL database   | postgres-mcp |

  Scenario: The tool corpus indexes tool descriptions alongside owner metadata
    When the tool corpus CT is constructed
    Then "create_pull_request" is present in CT with its description
    And the entry for "create_pull_request" records own(t) = "github-mcp"

  Scenario: The agent corpus indexes agent descriptions as top-level nodes
    When the agent corpus CA is constructed
    Then "github-mcp" is present in CA with its description
    And τ("github-mcp") = agent

  Scenario: Every tool entry in CT is typed as a tool
    When the tool corpus CT is constructed
    Then τ("create_pull_request") = tool
    And τ("run_query") = tool

  Scenario: The unified catalog C is the union CT ∪ CA
    When the unified catalog C is assembled
    Then C contains all entries from CT
    And C contains all entries from CA

  Scenario: The owner map own(·) enables tool-to-agent traversal at query time
    When the unified catalog C is assembled
    Then own("create_pull_request") resolves to "github-mcp"
    And own("list_issues") resolves to "github-mcp"
    And own("run_query") resolves to "postgres-mcp"

  Scenario: The similarity function s(q, ·) is defined over every entry in C
    Given the query "open a pull request"
    When similarity scores are computed against C
    Then a score s(q, e) is produced for every entry e in C
    And the scores rank "create_pull_request" and "github-mcp" above unrelated entries

  Scenario: Corpus scoring uses the similarity function provided by the configured embedding
    Given a mock embedding that returns 1.0 for any text containing "pull request"
    And returns 0.0 for all other texts
    When similarity scores are computed against C using the mock embedding
    Then "create_pull_request" receives a score of 1.0
    And "run_query" receives a score of 0.0
    And the mock embedding's score function is invoked for every entry in C
