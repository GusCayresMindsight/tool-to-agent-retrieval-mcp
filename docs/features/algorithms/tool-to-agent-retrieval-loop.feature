Feature: Tool-to-Agent Retrieval Loop – Algorithm 1
  Algorithm 1 "Combined Tool-Agent Top-K Retrieval" (Lumer et al., arXiv:2511.01854v2)
  is the online retrieval loop that converts a user query into a ranked list of at most
  K unique agents using the unified catalog C built offline.

  Input:   q – user query (after Stage 1 rewrite when enabled)
           C – unified catalog (see corpus-embedding.feature)
           N – candidate pool size, N >> K   (line 1: L ← TopN(q, C, N))
           K – desired number of unique agents to return
  Output:  A′ – set of K unique agents

  Loop invariant (lines 3-14):
    For each entity ℓ in L (ordered by descending similarity to q):
      • τ(ℓ) = agent → a ← ℓ          (add directly)
      • τ(ℓ) = tool  → a ← own(ℓ)    (resolve owner; skip if undefined)
    Add a to A only if a ∉ A (deduplication).
    Stop when |A| = K or all N candidates are exhausted.

  Background:
    Given a catalog containing the following agents:
      | agent_id     | description                                        |
      | github-mcp   | Interact with GitHub repositories, issues, and PRs |
      | postgres-mcp | Execute queries and manage PostgreSQL databases    |
      | slack-mcp    | Send messages and manage Slack workspaces          |
    And the catalog contains the following tools:
      | tool_id             | description                                    | owner        |
      | create_pull_request | Open a new pull request on a GitHub repository | github-mcp   |
      | list_issues         | List open issues for a repository              | github-mcp   |
      | run_query           | Execute a SQL query on a PostgreSQL database   | postgres-mcp |
      | send_message        | Send a message to a Slack channel              | slack-mcp    |

  Scenario: TopN retrieves N candidates from C before the deduplication loop runs
    When the query "open a pull request" is submitted with N=10 and K=1
    Then the loop ranks all entries in C by similarity to q
    And evaluates up to N=10 candidates to produce K=1 unique agent

  Scenario: An agent entry in the top-N is added to A directly (τ = agent branch)
    When the query "interact with GitHub repositories" is submitted with N=10 and K=1
    Then the top-ranked entry has τ = agent
    And "github-mcp" is returned as a direct match without owner resolution

  Scenario: A tool entry in the top-N resolves to its owner agent (τ = tool branch)
    When the query "open a pull request on a GitHub repository" is submitted with N=10 and K=1
    Then the top-ranked entry has τ = tool
    And own(create_pull_request) = "github-mcp" is resolved
    And "github-mcp" is returned as the owner of the matched tool

  Scenario: Duplicate candidates from the same agent count as one result entry
    When the query "manage GitHub issues and pull requests" is submitted with N=10 and K=5
    Then "github-mcp" appears exactly once in the result set
    And the result set contains at most 5 unique agents

  Scenario: The loop terminates early once K unique agents are collected
    When the query "open a pull request" is submitted with N=10 and K=1
    Then the loop stops as soon as 1 unique agent is identified
    And does not evaluate remaining candidates from the top-N pool

  Scenario: The result set is smaller than K when the catalog has fewer than K distinct agents
    When the query "open a pull request" is submitted with N=10 and K=10
    Then the result set contains at most 3 agents
    And the loop exits after exhausting all N candidates
