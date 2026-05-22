Feature: Embedding Interface
  The retrieval algorithm delegates similarity scoring to a pluggable Embedding.
  Any implementation must satisfy this contract so that embeddings can be swapped
  without changing Algorithm 1 or the corpus construction logic.

  An Embedding is a callable that accepts:
    q    – query string (already rewritten by Stage 1, or raw if rewriting is disabled)
    text – target text string (the concatenated name + description of an entry in C)
  and returns a float score in [0.0, 1.0], where higher means more similar.

  The similarity function s(q, ·) referenced in Algorithm 1 (Lumer et al.,
  arXiv:2511.01854v2) is fulfilled by any conforming Embedding.

  Scenario: An embedding accepts a query and target text and returns a float score
    Given an embedding implementation
    When it scores the query "open a pull request" against "Open a new pull request on GitHub"
    Then it returns a float score

  Scenario: Scores are in the range [0.0, 1.0]
    Given an embedding implementation
    When it scores any query against any target text
    Then the score is between 0.0 and 1.0 inclusive

  Scenario: An exact or near-exact text match produces a score of 1.0
    Given an embedding implementation
    When it scores the query "open pull request" against "open pull request"
    Then the score is 1.0

  Scenario: Completely unrelated texts produce a score of 0.0
    Given an embedding implementation
    When it scores the query "open pull request" against "send email to a colleague"
    Then the score is 0.0

  Scenario: A partial overlap produces a score strictly between 0.0 and 1.0
    Given an embedding implementation
    When it scores the query "open pull request" against "open a database connection"
    Then the score is greater than 0.0
    And the score is less than 1.0

  Scenario: The built-in token-overlap embedding is used when none is configured
    Given no embedding is explicitly configured
    When the retrieval algorithm runs a query against the catalog
    Then similarity is computed using the token-overlap embedding
