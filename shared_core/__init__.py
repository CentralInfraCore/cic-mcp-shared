"""shared_core: cross-session aggregation package for cic-mcp-shared.

Job: shared-cross-session-aggregator-implementation-001 — the FIRST actual
aggregator code in this repo (everything before this job was design-only
output/*.md reports + the shared_core.candidates Postgres schema, see
shared-core-storage-implementation-001).

Scope:
- shared_core.session_client: real subprocess + stdio MCP client for the
  cic-mcp-session MCP server (mirrors gateway_core.compile_context's
  SessionServerLaunchConfig pattern -- NOT reinvented here).
- shared_core.aggregator: cross-session min-max normalization, weight_score/
  recurrence_count computation (shared-weighting-model-001 formula, quoted
  not reinvented), and the shared_core.candidates INSERT.

No MCP server wiring of its own, no canonical promotion, no human review
flow -- see CLAUDE.md "Nem cél" / input.md "Nem cél".
"""
