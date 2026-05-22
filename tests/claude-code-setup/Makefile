PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
CORPUS       := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/.mcp-corpus.json)

export MCP_CORPUS_PATH := $(CORPUS)

UV := uv run --project $(PROJECT_ROOT)

.DEFAULT_GOAL := help

.PHONY: help check list search run claude env

help:
	@echo "Targets:"
	@echo "  make env                 Create .env with placeholders (skips if already exists)"
	@echo "  make claude              Launch Claude Code with the local MCP server wired in"
	@echo "  make claude EMBEDDER=X   Override embedder (anthropic | all-minilm-l6-v2 | token-overlap)"
	@echo "  make check               Corpus loads OK, prints agent/tool count"
	@echo "  make list                List every agent and its tools"
	@echo "  make search Q=...        Run a retrieval query (top 3 hits)"
	@echo "  make run                 Start the MCP stdio server (blocks until EOF)"
	@echo ""
	@echo "Embedder is read from TOOL_SELECTOR_EMBEDDING in .env (override with EMBEDDER=)."

env:
	@if [ -f .env ]; then \
		echo ".env already exists — skipping. Edit it directly to change values."; \
	else \
		printf '# Embedder selection (pick one, or leave unset for the default token-overlap)\n# Options: token-overlap | anthropic | all-minilm-l6-v2\n# TOOL_SELECTOR_EMBEDDING=token-overlap\n\n# Required for the anthropic embedder\nANTHROPIC_API_KEY=your-key-here\n\n# Downstream agent credentials (inherited by spawned subprocesses)\n# GITHUB_TOKEN=your-github-pat-here\n# POSTGRES_CONNECTION_STRING=postgresql://user:pass@localhost/dbname\n# SLACK_BOT_TOKEN=xoxb-your-token-here\n' > .env; \
		echo "Created .env — fill in your values before running make claude."; \
	fi

check:
	@$(UV) python -c "\
from tool_selector_mcp.cli import build_server; \
s = build_server(); \
n_tools = sum(len(a.tools) for a in s.corpus.agents.values()); \
print('OK —', len(s.corpus.agents), 'agents,', n_tools, 'tools')"

list:
	@$(UV) python -c "\
from tool_selector_mcp.cli import build_server; \
s = build_server(); \
[print(a.agent_id + ':', ', '.join(t.name for t in a.tools)) \
 for a in s.corpus.agents.values()]"

search:
	@test -n '$(Q)' || { echo 'Usage: make search Q="your query"'; exit 1; }
	@Q='$(Q)' $(UV) python -c "\
import os; \
from tool_selector_mcp.cli import build_server; \
s = build_server(); \
hits = s.search_tools(os.environ['Q'], k=3); \
[print(h.agent_id + '.' + (h.tool_name or '(agent)') + ':', h.description) \
 for h in hits]"

run:
	$(UV) tool-selector-mcp

# Claude Code reads project settings from the git root, not the CWD, so the
# .claude/settings.json here is ignored when you run plain `claude`.
# --mcp-config injects it explicitly; --strict-mcp-config keeps only this one.
# settings.json only stores the absolute path to start-mcp.sh; all other
# configuration (embedder, API key, corpus path) is handled by the script.
claude:
	@mkdir -p .claude
	@printf '{"mcpServers":{"tool-selector":{"command":"%s/start-mcp.sh"}}}\n' \
		"$(abspath $(dir $(lastword $(MAKEFILE_LIST))))" > .claude/settings.json
	EMBEDDER=$(EMBEDDER) claude --mcp-config .claude/settings.json --strict-mcp-config
