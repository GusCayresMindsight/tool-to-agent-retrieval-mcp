#!/usr/bin/env bash
# Launches the MCP server for live testing from tests/claude-code-setup/.
# Resolves all paths from this file's location — no hardcoded machine paths needed.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"

# Load .env if present (set -a exports every variable that is set)
if [ -f "$HERE/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$HERE/.env"
    set +a
fi

# EMBEDDER env var overrides TOOL_SELECTOR_EMBEDDING (set via `make claude EMBEDDER=x`)
EMBEDDING="${EMBEDDER:-${TOOL_SELECTOR_EMBEDDING:-}}"

EXTRA=()
case "$EMBEDDING" in
    anthropic)        EXTRA=(--with anthropic) ;;
    all-minilm-l6-v2) EXTRA=(--with sentence-transformers) ;;
esac

export MCP_CORPUS_PATH="$HERE/.mcp-corpus.json"
[ -n "$EMBEDDING" ] && export TOOL_SELECTOR_EMBEDDING="$EMBEDDING"

exec uv run --project "$PROJECT_ROOT" "${EXTRA[@]}" tool-selector-mcp
