Feature: All-MiniLM-L6-v2 Embedding
  The All-MiniLM-L6-v2 embedding uses the sentence-transformers model of the same
  name to produce dense vector representations of text. Similarity is the cosine
  similarity between the encoded query and target vectors, rescaled to [0.0, 1.0].

  This model runs locally, requires no API key, and is one of the eight embeddings
  evaluated in "Tool-to-Agent Retrieval" (Lumer et al., arXiv:2511.01854v2, Table 2).

  Scenario: The embedding encodes query and target into dense vectors and returns cosine similarity
    Given an All-MiniLM-L6-v2 embedding
    When it scores the query "open a pull request" against "Open a new pull request on GitHub"
    Then it encodes both strings into dense vectors
    And returns their cosine similarity as the score

  Scenario: The model is loaded once and reused across score calls
    Given an All-MiniLM-L6-v2 embedding instantiated once
    When it scores multiple query-text pairs in sequence
    Then the sentence-transformers model is loaded only on first use
    And the same model instance is reused for all subsequent calls

  Scenario: The All-MiniLM-L6-v2 embedding satisfies the Embedding interface contract
    Given an All-MiniLM-L6-v2 embedding
    When it scores any query against any target text
    Then the score is between 0.0 and 1.0 inclusive
    And it returns a float score
