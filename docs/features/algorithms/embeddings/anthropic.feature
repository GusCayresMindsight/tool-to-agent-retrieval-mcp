Feature: Anthropic Embedding
  The Anthropic embedding scores semantic similarity by prompting Claude via the
  Anthropic messages API. Given a query q and target text, it asks Claude to judge
  how relevant the target is to the query and return a float in [0.0, 1.0].

  This embedding requires an ANTHROPIC_API_KEY and incurs per-token costs.
  It is suitable for production use when high semantic precision is required and
  latency of an API call per catalog entry is acceptable.

  Scenario: The embedding sends a scoring prompt to the Anthropic messages API
    Given an Anthropic embedding configured with a valid API key
    When it scores the query "open a pull request" against "Open a new pull request on GitHub"
    Then it issues a request to the Anthropic messages API
    And returns the float score extracted from the response

  Scenario: A single Anthropic client instance is reused across multiple score calls
    Given an Anthropic embedding instantiated once
    When it scores multiple query-text pairs in sequence
    Then the same Anthropic client is used for every call

  Scenario: The Anthropic embedding satisfies the Embedding interface contract
    Given an Anthropic embedding
    When it scores any query against any target text
    Then the score is between 0.0 and 1.0 inclusive
    And it returns a float score
