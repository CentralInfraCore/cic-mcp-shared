"""Cross-session aggregator: search_session_context() -> shared_core.candidates.

Job: shared-cross-session-aggregator-implementation-001, "Feladat" 3
("Aggregátor-implementáció").

This module:
  1. Calls the REAL cic-mcp-session MCP `search_session_context(session_id,
     query, limit)` tool, once per session_id, via a real subprocess + stdio
     handshake (shared_core.session_client, mirroring
     gateway_core/compile_context.py:70 SessionServerLaunchConfig -- see
     that module's docstring).
  2. Combines the per-session `fused_score` results via SESSION-WISE MIN-MAX
     NORMALIZATION, then summation -- per jobs/shared-cross-session-search-001/
     output/shared-cross-session-search.md line 309 ("Döntés:
     session-enkénti min-max normalizálás, majd egyszerű összegzés -- NEM
     nyers fused_score összegzés/átlagolás."). NOT reinvented: the
     normalization formula `(score - min) / (max - min)` (or 1.0 if only one
     row) and the "sum, not average, across sessions" combination rule are
     quoted from that report, lines 321-336.
  3. Computes `weight_score` and `recurrence_count` per
     jobs/shared-weighting-model-001/output/shared-weighting-model.md lines
     290-298:

         weight_score = cross_session_score
                        + factory_linkage_bonus
                        + recency_bonus
         recurrence_count = number of sessions with non-zero normalized
                             relevance

     `factory_linkage_bonus` and `recency_bonus` are documented there as
     "additive, fixed value" bonuses whose CONCRETE numeric value (and the
     promotion THRESHOLD) is explicitly left to a future implementation
     job (shared-weighting-model.md lines 308-309: "A THRESHOLD konkrét
     numerikus értéke implementációs döntés (NEM ennek a jobnak a tárgya)").
     THIS job's "Nem cél" also excludes "a weight_score/recurrence_count
     formula újradefiniálása" -- so the ADDITIVE STRUCTURE (sum of three
     named terms, recurrence_count as a separate AND-gated condition) is
     followed exactly, while the bonus magnitudes are implementation-level
     constants (named, not silently inlined) that this job is free to pick.
  4. Inserts ONE shared_core.candidates row (shared-core-storage-
     implementation-001/output/shared-core-storage-schema.sql) per
     aggregation run, with `provenance_refs` JSONB built from the
     {session_id, chunk_id, turn_id, content_hash} pointer shape documented
     at shared-cross-session-search.md line 372 (quoted in the schema's own
     comment at shared-core-storage-schema.sql:90-96 -- not reinvented).

Not in scope (input.md "Nem cél"): schema changes, formula redefinition,
canonical promotion/review, historical-import-runner-001.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg

from shared_core.session_client import (
    SessionServerLaunchConfig,
    search_session_context,
    session_mcp_client,
)

# --- shared-weighting-model-001 bonus/threshold constants -----------------
# Magnitudes are an implementation-level choice (shared-weighting-model.md
# line 308-309 explicitly defers THRESHOLD/bonus VALUES to "a future
# implementation job" -- this job). The ADDITIVE STRUCTURE around these
# constants (weight_score = cross_session_score + factory_linkage_bonus +
# recency_bonus, recurrence_count as a separate AND-gated condition) is the
# part that is NOT invented here -- see module docstring point 3.
FACTORY_LINKAGE_BONUS = 0.1
RECENCY_BONUS = 0.1
RECENCY_WINDOW_DAYS = 30
PROMOTION_WEIGHT_THRESHOLD = 0.5
PROMOTION_MIN_RECURRENCE = 2


def decide_trust_level(weight_score: float, recurrence_count: int) -> str:
    """Determine the trust level for a new shared_core.candidates row.

    Applies the promotion-candidate gating contract from shared-weighting-
    model-001 (lines 290-298): both conditions must hold simultaneously
    (AND, not OR) for a row to be promoted to 'candidate'. If either
    condition fails, the row is inserted as 'mixed' -- the lowest trust
    level allowed for an automatically generated row by the schema CHECK
    constraint ('mixed', 'candidate', 'reviewed_shared'). 'reviewed_shared'
    and 'canonical' are never set here -- they are always the result of a
    separate human review flow.
    """
    if recurrence_count >= PROMOTION_MIN_RECURRENCE and weight_score >= PROMOTION_WEIGHT_THRESHOLD:
        return "candidate"
    return "mixed"


@dataclass(frozen=True)
class SharedStoreConfig:
    """DB connection parameters for shared_core.candidates writes, sourced
    from env vars -- same SESSION_STORE_PG_* var names as
    session_store.envelope_writer.SessionStoreConfig.from_env() (this job's
    test fixtures point both the session MCP subprocess AND the
    shared_core.candidates INSERT at the SAME Postgres instance, per
    input.md's single-Postgres-instance setup). No hardcoded connection
    string.
    """

    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "SharedStoreConfig":
        import os

        return cls(
            host=os.environ.get("SESSION_STORE_PG_HOST", os.environ.get("PGHOST", "localhost")),
            port=int(os.environ.get("SESSION_STORE_PG_PORT", os.environ.get("PGPORT", "5432"))),
            dbname=os.environ.get("SESSION_STORE_PG_DB", os.environ.get("PGDATABASE", "postgres")),
            user=os.environ.get("SESSION_STORE_PG_USER", os.environ.get("PGUSER", "postgres")),
            password=os.environ.get(
                "SESSION_STORE_PG_PASSWORD", os.environ.get("PGPASSWORD", "")
            ),
        )

    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )


@dataclass
class CrossSessionAggregationResult:
    """Everything produced by one aggregate_cross_session() run, returned
    so the caller (and tests) can inspect the actual computed values rather
    than re-deriving them from the DB row alone.
    """

    candidate_id: str
    keyword_description: str
    cross_session_score: float
    factory_linkage_bonus: float
    recency_bonus: float
    weight_score: float
    recurrence_count: int
    provenance_refs: list[dict[str, Any]]
    per_session_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _min_max_normalize(scores: list[float]) -> list[float]:
    """Session-wise min-max normalization of fused_score values into [0, 1].

    Per shared-cross-session-search.md line 321-330 ("A normalizálás
    módja"): `(score - min) / (max - min)` across the session's own
    returned rows, or 1.0 if only one row is returned (no spread to
    normalize against). NOT reimplemented differently here.
    """
    if not scores:
        return []
    if len(scores) == 1:
        return [1.0]
    lo = min(scores)
    hi = max(scores)
    if hi == lo:
        # All rows tied -- no within-session spread; treat all as maximally
        # relevant (1.0), consistent with the single-row case above.
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


async def _query_one_session(
    session, session_id: str, query: str, limit: int
) -> list[dict[str, Any]]:
    """One search_session_context() round-trip for one session_id, per the
    serial (not concurrent) per-session call pattern documented at
    shared-cross-session-search.md "Soros (nem párhuzamos) végrehajtás
    session-enkénti" (lines 280-289 of that report).
    """
    return await search_session_context(session, session_id, query, limit)


async def _aggregate_cross_session_async(
    keyword_description: str,
    session_ids: list[str],
    *,
    session_repo_root: Path,
    shared_config: SharedStoreConfig | None = None,
    per_session_limit: int = 20,
    linked_factory_job_ids: list[str] | None = None,
    last_evidence_at: datetime | None = None,
    now: datetime | None = None,
) -> CrossSessionAggregationResult:
    """Async implementation -- does the REAL subprocess + stdio handshake.

    Synchronous callers should use aggregate_cross_session() below, which
    wraps this with asyncio.run() -- same split as
    gateway_core/compile_context.py's _compile_context_async() /
    compile_context() (lines 152/354), so this module is usable from plain
    pytest tests without adding a pytest-asyncio dependency.

    Run one full aggregation cycle:

      1. real subprocess + stdio MCP search_session_context() per session_id
      2. session-wise min-max normalization + summation -> cross_session_score
      3. weight_score / recurrence_count per shared-weighting-model-001
      4. INSERT one shared_core.candidates row

    Args:
        keyword_description: the short keyword/cluster description query
            text, used verbatim as the `query` argument to
            search_session_context() for every session_id (this job's
            "Nem cél": the ORIGIN of this string -- e.g. LLM extraction --
            is explicitly out of scope; it is taken as a given input here,
            same framing as shared-cross-session-search.md's "Findings" #2).
        session_ids: ordered list of session_id strings to query, ALREADY
            filtered/ordered by the caller (get_session_status-based
            filtering and last_seen_at-descending ordering are the calling
            job's contract per shared-cross-session-search.md "Hány
            session-t kérdez le" -- not reimplemented inside this function).
        session_repo_root: path to a cic-mcp-session checkout with
            .venv-host/bin/python already built (make deps.local) -- passed
            straight into SessionServerLaunchConfig.
        shared_config: shared_core.candidates DB connection config (defaults
            to SharedStoreConfig.from_env()).
        per_session_limit: `limit` argument forwarded to every
            search_session_context() call.
        linked_factory_job_ids: optional factory job id list. If non-empty,
            factory_linkage_bonus is added to weight_score (shared-
            weighting-model.md: "additív, fix érték, ha
            linked_factory_job_ids[] nem üres").
        last_evidence_at: optional timestamp of the most recent evidence
            for this candidate. If set and within RECENCY_WINDOW_DAYS of
            `now`, recency_bonus is added (shared-weighting-model.md:
            "additív, fix érték, ha last_evidence_at az utolsó N napban
            van").
        now: injectable "current time" for deterministic recency tests
            (defaults to datetime.now(timezone.utc)).

    Returns:
        CrossSessionAggregationResult with the actual computed values AND
        the candidate_id of the inserted shared_core.candidates row.
    """
    shared_config = shared_config or SharedStoreConfig.from_env()
    linked_factory_job_ids = linked_factory_job_ids or []
    now = now or datetime.now(timezone.utc)

    launch_config = SessionServerLaunchConfig(repo_root=session_repo_root)

    per_session_results: dict[str, list[dict[str, Any]]] = {}
    per_session_normalized: dict[str, list[float]] = {}

    async with session_mcp_client(launch_config) as session:
        for session_id in session_ids:
            # Serial, one MCP round-trip per session_id (shared-cross-
            # session-search.md "Soros (nem párhuzamos) végrehajtás").
            rows = await _query_one_session(
                session, session_id, keyword_description, per_session_limit
            )
            per_session_results[session_id] = rows
            scores = [row["fused_score"] for row in rows]
            per_session_normalized[session_id] = _min_max_normalize(scores)

    # cross_session_score: session-wise min-max normalized values, SUMMED
    # (not averaged) across sessions -- shared-cross-session-search.md line
    # 309 / "A kombinálás" (lines 333-339).
    cross_session_score = sum(
        sum(normalized) for normalized in per_session_normalized.values()
    )

    # recurrence_count: number of sessions with at least one non-zero
    # normalized relevance value -- shared-weighting-model-001 "Feladat" 3 /
    # input.md "recurrence_count (hány session-ben volt nem-nulla
    # normalizált relevancia)".
    recurrence_count = sum(
        1 for normalized in per_session_normalized.values() if any(v > 0 for v in normalized)
    )

    factory_linkage_bonus = FACTORY_LINKAGE_BONUS if linked_factory_job_ids else 0.0

    recency_flag = bool(
        last_evidence_at is not None
        and (now - last_evidence_at) <= timedelta(days=RECENCY_WINDOW_DAYS)
    )
    recency_bonus = RECENCY_BONUS if recency_flag else 0.0

    # weight_score = cross_session_score + factory_linkage_bonus +
    # recency_bonus -- shared-weighting-model.md lines 290-292, quoted
    # verbatim in the additive structure (NOT reinvented).
    weight_score = cross_session_score + factory_linkage_bonus + recency_bonus

    provenance_refs = _build_provenance_refs(per_session_results)

    candidate_id = _insert_candidate(
        shared_config,
        keyword_description=keyword_description,
        weight_score=weight_score,
        recurrence_count=recurrence_count,
        linked_factory_job_ids=linked_factory_job_ids,
        last_evidence_at=last_evidence_at,
        recency_flag=recency_flag,
        provenance_refs=provenance_refs,
    )

    return CrossSessionAggregationResult(
        candidate_id=candidate_id,
        keyword_description=keyword_description,
        cross_session_score=cross_session_score,
        factory_linkage_bonus=factory_linkage_bonus,
        recency_bonus=recency_bonus,
        weight_score=weight_score,
        recurrence_count=recurrence_count,
        provenance_refs=provenance_refs,
        per_session_results=per_session_results,
    )


def aggregate_cross_session(
    keyword_description: str,
    session_ids: list[str],
    *,
    session_repo_root: Path,
    shared_config: SharedStoreConfig | None = None,
    per_session_limit: int = 20,
    linked_factory_job_ids: list[str] | None = None,
    last_evidence_at: datetime | None = None,
    now: datetime | None = None,
) -> CrossSessionAggregationResult:
    """Public, synchronous entry point -- see
    _aggregate_cross_session_async() for the full parameter docs and the
    real-subprocess/normalization/weighting/INSERT behavior.
    """
    import asyncio

    return asyncio.run(
        _aggregate_cross_session_async(
            keyword_description,
            session_ids,
            session_repo_root=session_repo_root,
            shared_config=shared_config,
            per_session_limit=per_session_limit,
            linked_factory_job_ids=linked_factory_job_ids,
            last_evidence_at=last_evidence_at,
            now=now,
        )
    )


def _build_provenance_refs(
    per_session_results: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build the provenance_refs JSONB payload:
    {session_id, chunk_id, turn_id, content_hash} pointers -- the structure
    documented at shared-cross-session-search.md line 372 (quoted in
    shared-core-storage-schema.sql:90-96's own comment), pointers only,
    NEVER the chunk text itself.
    """
    refs: list[dict[str, Any]] = []
    for session_id, rows in per_session_results.items():
        for row in rows:
            text = row.get("text", "")
            content_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
            refs.append(
                {
                    "session_id": session_id,
                    "chunk_id": row.get("chunk_id"),
                    "turn_id": row.get("turn_id"),
                    "content_hash": content_hash,
                }
            )
    return refs


def _insert_candidate(
    config: SharedStoreConfig,
    *,
    keyword_description: str,
    weight_score: float,
    recurrence_count: int,
    linked_factory_job_ids: list[str],
    last_evidence_at: datetime | None,
    recency_flag: bool,
    provenance_refs: list[dict[str, Any]],
) -> str:
    """INSERT one shared_core.candidates row using the EXISTING schema
    (shared-core-storage-implementation-001/output/shared-core-storage-
    schema.sql) -- no schema changes, no new columns. `trust` is determined
    by decide_trust_level(weight_score, recurrence_count): 'candidate' if
    both recurrence_count >= PROMOTION_MIN_RECURRENCE and weight_score >=
    PROMOTION_WEIGHT_THRESHOLD, 'mixed' otherwise. 'reviewed_shared' and
    'canonical' are never set here -- they are always the result of a
    separate human review flow (cic-mcp-shared/CLAUDE.md "Trust modell").
    `canonical` is left at its DEFAULT FALSE (not set explicitly) -- the
    canonical_requires_reviewed_shared CHECK constraint would reject
    canonical=true at trust='candidate' anyway.
    """
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO shared_core.candidates (
                    keyword_description,
                    trust,
                    weight_score,
                    recurrence_count,
                    linked_factory_job_ids,
                    last_evidence_at,
                    recency_flag,
                    provenance_refs
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING candidate_id
                """,
                (
                    keyword_description,
                    decide_trust_level(weight_score, recurrence_count),
                    weight_score,
                    recurrence_count,
                    linked_factory_job_ids,
                    last_evidence_at,
                    recency_flag,
                    json.dumps(provenance_refs),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return str(row[0])
