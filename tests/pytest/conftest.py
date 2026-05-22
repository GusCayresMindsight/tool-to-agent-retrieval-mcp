"""Shared fixtures for the tool-selector-mcp BDD test suite.

`bdd_features_base_dir` is configured in pyproject.toml so that
`scenarios("<name>.feature")` calls resolve against docs/features/.

The per-feature step modules are loaded as pytest plugins so that their
`@given`/`@when`/`@then` registrations land in fixture sources pytest
discovers (plain `import` of a module does not register its fixtures with
the pytest fixture manager).
"""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = [
    "steps.installation_steps",
    "steps.mcp_server_steps",
    "steps.corpus_configuration_steps",
    "steps.server_tools_steps",
    "steps.tool_to_agent_retrieval_steps",
    "steps.corpus_embedding_steps",
    "steps.embedding_interface_steps",
    "steps.retrieval_loop_steps",
    "steps.scripted_embedding_steps",
    "steps.anthropic_embedding_steps",
    "steps.minilm_embedding_steps",
]


@pytest.fixture
def bdd_state() -> dict[str, Any]:
    """A scratch dict for steps to thread small values across a scenario."""
    return {}
