Feature: Scripted Embedding
  The Scripted embedding assigns fixed scores to specific texts via an explicit
  lookup table supplied at construction time. Any text not present in the table
  returns a configurable default score.

  It satisfies the Embedding interface (see embedding-interface.feature) but is
  not intended as a production retrieval solution. Its value is in tests: by
  wiring known scores to known texts, test authors can exercise the retrieval
  loop and corpus logic with fully deterministic, dependency-free behaviour.

  Scenario: Returns the configured score for a known text
    Given a scripted embedding configured with:
      | text                                           | score |
      | Open a new pull request on a GitHub repository | 1.0   |
      | Execute a SQL query on a PostgreSQL database   | 0.0   |
    When it scores any query against "Open a new pull request on a GitHub repository"
    Then it returns 1.0

  Scenario: Returns the default score for an unconfigured text
    Given a scripted embedding with default score 0.5
    When it scores any query against a text that is not in the lookup table
    Then it returns 0.5

  Scenario: The score is independent of the query
    Given a scripted embedding configured with a fixed score for a target text
    When the same target text is scored against two different queries
    Then both calls return the same score

  Scenario: The scripted embedding satisfies the Embedding interface contract
    Given a scripted embedding
    When it scores any query against any target text
    Then the score is between 0.0 and 1.0 inclusive
    And it returns a float score
