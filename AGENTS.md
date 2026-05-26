# AGENTS.md

Guidance for AI coding agents working on `tool-to-agent-retrieval-mcp`. Read this file before doing anything else.

## Project

`tool-to-agent-retrieval-mcp` is an MCP server that, given a natural language query, selects the best-suited downstream agent from a corpus and forwards a tool call to it. It is distributed via `uvx`. The behavior of the system is specified by the Gherkin feature files in `docs/features/` — **those files are the source of truth, not the code**.

## Repo layout

- `docs/features/*.feature` — Gherkin specs. Source of truth for behavior.
- `src/tool_selector_mcp/` — production code (currently a stub).
- `tests/pytest/test_features.py` — single test module that calls `scenarios()` for every feature file.
- `tests/pytest/steps/<feature>_steps.py` — step definitions, one module per feature file. Each module is imported by `test_features.py` to register its decorators.
- `pyproject.toml` — sets `bdd_features_base_dir = "docs/features"` so `scenarios("foo.feature")` resolves against that directory.

## Required workflow: BDD-first, with hard gates

Production code is the **last** thing you write. Work outside-in, and **do not cross a gate until the user has explicitly approved** what's inside it. Silence is not approval; "ok" or "go ahead" or "approved" is.

### Gate 1 — Feature file approval

Before writing or modifying any step or any production code:

1. Locate the relevant `.feature` file in `docs/features/`, or propose a new one.
2. Show the user the full Gherkin you intend to add or change — scenarios, Background, Scenario Outline, Examples, all of it. Quote it inline in the message; don't paraphrase.
3. Iterate with the user on wording, scenario boundaries, and naming.
4. Get explicit approval before moving on.

### Gate 2 — Step implementation approval

Once the feature file is approved, before writing any production code:

1. Propose the step definitions in `tests/pytest/steps/<feature>_steps.py` — the `@given`/`@when`/`@then` bodies, the parsers (`parsers.parse`, `parsers.cfparse`), the fixtures, and what each step asserts against.
2. Show the user the step bodies. Call out any helper fixtures and where the test boundary lives (in-process call vs subprocess vs network).
3. Get explicit approval before moving on.

Steps may reference production functions that don't exist yet — that is expected. The test failing at import or call site is the signal that drives Gate 3.

### Gate 3 — Implementation

Only after Gates 1 and 2 are passed, write the minimum production code in `src/tool_selector_mcp/` to make the failing scenarios pass. Do not refactor, extract helpers, or add scope beyond what the active scenarios require. When the scenarios go green, stop.

## BDD best practices (apply when drafting or reviewing feature files)

- **Declarative, not imperative.** Describe *what* from the user's perspective, not *how*. "When the user asks for an agent that can open a pull request" ✅. "When the client POSTs `{...}` to `/search`" ❌.
- **One scenario, one behavior.** If a scenario chains "And then... And then..." past a couple of steps, split it.
- **Given = preconditions/state. When = the single action under test. Then = observable outcome.** Don't assert in Given. Don't set up state in When.
- **Concrete examples, not abstract rules.** Use real corpus entries, real queries, real agent names. Reuse the names already in the existing features (`github-mcp`, `slack-mcp`, `postgres-mcp`, etc.) for consistency.
- **No incidental detail.** Don't pin behavior to things the test doesn't actually care about (ordering, formatting, casing) unless that *is* the behavior.
- **Background is for shared setup**, not for hiding test data. If a Background is only used by one scenario, or grows past ~4 lines, inline it.
- **Scenario Outline + Examples** for N variations of the same behavior differing only in inputs.
- **Reusable step phrasing.** Steps should describe a general concept ("a corpus containing X"), not a one-off ("the corpus from scenario 3").
- **Domain language, not code language.** Steps reference "agents", "tools", "the corpus" — not classes, modules, or file paths.

## Step implementation best practices

- **One step module per feature file** (current layout). Decorators register on import; `test_features.py` already imports each module.
- **Use `pytest_bdd.parsers`** (`parse`, `cfparse`, `re`) for parameterized steps. Avoid hand-written regex unless you must.
- **Steps assert against observable outputs**, not internal state. If you find yourself reaching into private attributes to make an assertion pass, push back — the scenario is probably testing the wrong thing.
- **Fixtures over module globals** for state shared between steps in a scenario. `pytest-bdd` injects pytest fixtures into step functions.
- **`target_fixture=`** when a Given/When produces a value that later steps consume.
- **Reuse existing steps before adding new ones.** Grep `tests/pytest/steps/` first. A step phrased "the corpus contains agent X" should not be re-invented as "the corpus has an agent named X".

## Anti-patterns — stop and ask the user if you catch yourself doing any of these

- Writing production code before a scenario covers it.
- "Fixing" a failing scenario by editing the scenario instead of the code.
- Marking a scenario `@skip` or `@wip` to keep the suite green.
- Mocking the thing the scenario is supposed to verify (e.g. mocking the retrieval algorithm in a retrieval scenario).
- Inventing tool names, agent names, or corpus keys that aren't in the existing features without confirming the naming.
- Adding implementation not required by an approved scenario "because we'll need it later".

## Quick reference — commands

- Build: `uv build`
- Sync dev deps: `uv sync --extra dev`
- Collect tests: `uv run --extra dev pytest tests/pytest --collect-only`
- Run tests: `uv run --extra dev pytest tests/pytest`
- Launch the stub locally: `uv run tool-to-agent-retrieval-mcp`
