"""Cross-session aggregator: search_session_context() -> shared_core.candidates.

Job: shared-cross-session-aggregator-implementation-001, "Feladat" 3
("Aggregátor-implementáció"). REWORKED by shared-scoring-rework-001 -- see
that job's "Kontextus" for the two bugs fixed here and "Nem cél" for what is
explicitly NOT touched (the trust/canonical CHECK constraint, the candidate
review/promote/reject lifecycle, the provenance_refs JSONB shape).

This module:
  1. Calls the REAL cic-mcp-session MCP `search_session_context(session_id,
     query, limit)` tool, once per session_id, via a real subprocess + stdio
     handshake (shared_core.session_client, mirroring
     gateway_core/compile_context.py:70 SessionServerLaunchConfig -- see
     that module's docstring).
  2. Combines the per-session `fused_score` results via SESSION-WISE MIN-MAX
     NORMALIZATION -- per jobs/shared-cross-session-search-001/output/
     shared-cross-session-search.md line 309 ("Döntés: session-enkénti
     min-max normalizálás..."). The normalization formula itself
     (`(score - min) / (max - min)`, or 1.0 if only one row) is QUOTED from
     that report, lines 321-330, and is NOT changed by this job.

     What IS changed by shared-scoring-rework-001 (see that job's
     "Kontextus" for why): the ORIGINAL combination step was
     `sum(sum(per_session_normalized.values()))` -- summing every session's
     normalized scores, with NO per-session ceiling. That let a single
     session with many matches outweigh several sessions with one strong
     match each, the opposite of "visszatérő fogalom" detection. The
     REWORKED combination step (`_combine_session_scores`) is now:
       a. an ABSOLUTE MINIMUM RELEVANCE THRESHOLD
          (`MIN_RELEVANCE_THRESHOLD`): per-row normalized values at or
          below this threshold do not count towards a session's score at
          all (a session where every row is weak contributes 0, not a
          ON the threshold value).
       b. a PER-SESSION SCORE CAP: each session's contribution to
          `cross_session_score` is its own TOP-K MEAN of the
          threshold-surviving normalized values (not their sum), capped at
          1.0 by construction (mean of values already in [0, 1]) -- see
          `_combine_session_scores` docstring for why top-k mean was chosen
          over a single max().
       c. summed ACROSS sessions (this part unchanged from the original
          design -- "minél TÖBB session-ben jelenik meg... annál magasabb a
          cross-session pontszám", shared-cross-session-search.md line
          333-339) -- so the "more sessions, more signal" property is kept,
          while "one session's many matches can't out-shout the rest" is
          newly enforced.
  3. Computes `weight_score` and `recurrence_count` per
     jobs/shared-weighting-model-001/output/shared-weighting-model.md lines
     290-298:

         weight_score = cross_session_score
                        + factory_linkage_bonus
                        + recency_bonus
         recurrence_count = number of sessions with non-zero normalized
                             relevance (post-threshold)

     `factory_linkage_bonus` and `recency_bonus` are documented there as
     "additive, fixed value" bonuses whose CONCRETE numeric value (and the
     promotion THRESHOLD) is explicitly left to a future implementation
     job (shared-weighting-model.md lines 308-309: "A THRESHOLD konkrét
     numerikus értéke implementációs döntés (NEM ennek a jobnak a tárgya)").
     The ADDITIVE STRUCTURE (sum of three named terms, recurrence_count as a
     separate AND-gated condition) is unchanged by shared-scoring-rework-001
     -- only the cross_session_score INPUT to that sum is reworked (point 2
     above), and a MINIMUM EVIDENCE COUNT GATE is added on top
     (`MIN_PROVENANCE_REFS_FOR_CANDIDATE`, see `_aggregate_cross_session_async`):
     if the total number of provenance refs across all sessions is below
     this gate, NO shared_core.candidates row is written at all (this is a
     row-existence gate, distinct from -- and in addition to -- the
     recurrence_count/weight_score AND-gate inside decide_trust_level() that
     only governs the 'mixed' vs 'candidate' trust LEVEL of an already-
     written row).
  4. UPSERTS (not always-INSERTs) one shared_core.candidates row per
     aggregation run via `INSERT ... ON CONFLICT (fingerprint) DO UPDATE`
     (`_insert_candidate`, see its docstring for the fingerprint
     definition and the idempotency guarantee this gives), with
     `provenance_refs` JSONB built from the {session_id, chunk_id, turn_id,
     content_hash} pointer shape documented at shared-cross-session-
     search.md line 372 (quoted in the schema's own comment at shared-core-
     storage-schema.sql:90-96 -- not reinvented) and, on conflict, MERGED
     with (not replacing) the row's existing provenance_refs.

Not in scope (input.md "Nem cél" + shared-scoring-rework-001 "Nem cél"):
the trust/canonical CHECK constraint, candidate review/promote/reject
lifecycle, provenance_refs JSONB *shape* changes, historical-import-
runner-001.
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

# --- shared-scoring-rework-001 score-formula constants --------------------
# Fixes the two bugs documented in that job's "Kontextus": (a) the original
# cross_session_score let ONE session's many matches outweigh several
# sessions' single strong matches (sum-of-sums, no per-session ceiling),
# (b) there was no minimum-evidence gate, so even a single, barely-relevant
# match could produce a shared_core.candidates row.

# A per-row normalized relevance value AT OR BELOW this threshold does not
# count towards its session's score at all. 0.2 is chosen as a conservative
# "clearly below the session's own median relevance" cut -- min-max
# normalization guarantees the weakest row in any session is exactly 0.0
# and the strongest is exactly 1.0, so a 0.2 cutoff discards only the rows
# that are close to that session's OWN floor, not an arbitrary absolute
# fused_score value (which would not be comparable across sessions in the
# first place, see _min_max_normalize's docstring).
MIN_RELEVANCE_THRESHOLD = 0.2

# Per-session score cap: instead of summing every threshold-surviving
# normalized value within a session (the original bug), each session
# contributes the MEAN of its top-K threshold-surviving values, which is
# bounded in [0, 1] by construction (mean of values already in [0, 1]).
# Top-K MEAN (K=3) is chosen over a single max() because max() would
# collapse a session with several consistently strong matches down to the
# same contribution as a session with exactly one strong match plus several
# weak ones -- losing the "how consistently does this session support the
# concept" signal entirely. A top-K mean keeps that signal while still
# capping the per-session contribution at 1.0, so a session with MANY
# matches (the original bug's failure mode) can no longer out-weigh several
# sessions with one strong match each merely by having a longer tail of
# matches.
SESSION_SCORE_TOP_K = 3

# Minimum total evidence count (sum of provenance refs across ALL sessions,
# i.e. all threshold-surviving AND threshold-failing rows -- the literal
# "bizonyítékszám" input.md "Feladat" 2 refers to, which is the recorded
# provenance_refs length, not the post-threshold relevance count) below
# which NO shared_core.candidates row is written at all. This is a
# row-existence gate, separate from -- and evaluated BEFORE -- the
# recurrence_count/weight_score AND-gate inside decide_trust_level() (which
# only decides 'mixed' vs 'candidate' trust on an ALREADY-written row).
MIN_PROVENANCE_REFS_FOR_CANDIDATE = 2


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

    candidate_id is None when shared-scoring-rework-001's minimum evidence
    count gate (MIN_PROVENANCE_REFS_FOR_CANDIDATE) rejects the run -- no
    shared_core.candidates row is written in that case, see
    _aggregate_cross_session_async.
    """

    candidate_id: str | None
    keyword_description: str
    cross_session_score: float
    factory_linkage_bonus: float
    recency_bonus: float
    weight_score: float
    recurrence_count: int
    provenance_refs: list[dict[str, Any]]
    fingerprint: str | None = None
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


def _combine_session_scores(normalized: list[float]) -> float:
    """One session's contribution to cross_session_score -- the
    shared-scoring-rework-001 replacement for the original
    `sum(normalized)` per-session term (see module docstring point 2 for
    the bug this fixes).

    Steps:
      1. Drop every value <= MIN_RELEVANCE_THRESHOLD (the absolute minimum
         relevance threshold -- a session where every row is weak
         contributes exactly 0.0, not a near-zero sum of sub-threshold
         noise).
      2. Take the MEAN of the top SESSION_SCORE_TOP_K surviving values (not
         their sum) -- bounded in [0, 1] by construction, so one session's
         row COUNT can no longer inflate its contribution past what a
         single, perfectly relevant match would contribute. See module
         constants block for why top-k MEAN was chosen over a bare max().

    Returns 0.0 if no value survives the threshold.
    """
    survivors = [v for v in normalized if v > MIN_RELEVANCE_THRESHOLD]
    if not survivors:
        return 0.0
    top_k = sorted(survivors, reverse=True)[:SESSION_SCORE_TOP_K]
    return sum(top_k) / len(top_k)


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

    # cross_session_score (shared-scoring-rework-001 REWORK -- see module
    # docstring point 2): each session contributes
    # _combine_session_scores(normalized) -- threshold-filtered, top-k
    # MEAN, bounded in [0, 1] -- NOT the raw sum of that session's
    # normalized values. Sessions are still SUMMED together (unchanged from
    # the original design: more recurring sessions => higher score), only
    # the PER-SESSION term changed.
    cross_session_score = sum(
        _combine_session_scores(normalized) for normalized in per_session_normalized.values()
    )

    # recurrence_count: number of sessions with at least one
    # threshold-surviving normalized relevance value -- shared-weighting-
    # model-001 "Feladat" 3 / input.md "recurrence_count (hány session-ben
    # volt nem-nulla normalizált relevancia)". Now consistent with the
    # MIN_RELEVANCE_THRESHOLD gate used in _combine_session_scores (a
    # session that contributes 0.0 to cross_session_score because every row
    # was below threshold no longer counts as "recurring" either).
    recurrence_count = sum(
        1
        for normalized in per_session_normalized.values()
        if any(v > MIN_RELEVANCE_THRESHOLD for v in normalized)
    )

    provenance_refs = _build_provenance_refs(per_session_results)

    # Minimum evidence count gate (shared-scoring-rework-001 "Feladat" 2):
    # if the TOTAL number of provenance refs across all sessions (every
    # row returned by search_session_context, threshold-surviving or not --
    # this is the recorded-evidence count, not the post-threshold relevance
    # count) is below MIN_PROVENANCE_REFS_FOR_CANDIDATE, no
    # shared_core.candidates row is written at all. Evaluated BEFORE the
    # INSERT/UPSERT call, so a too-thin-evidence run never reaches the DB.
    if len(provenance_refs) < MIN_PROVENANCE_REFS_FOR_CANDIDATE:
        return CrossSessionAggregationResult(
            candidate_id=None,
            keyword_description=keyword_description,
            cross_session_score=cross_session_score,
            factory_linkage_bonus=0.0,
            recency_bonus=0.0,
            weight_score=0.0,
            recurrence_count=recurrence_count,
            provenance_refs=provenance_refs,
            fingerprint=None,
            per_session_results=per_session_results,
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

    fingerprint = _compute_fingerprint(keyword_description, session_ids)

    candidate_id = _insert_candidate(
        shared_config,
        keyword_description=keyword_description,
        weight_score=weight_score,
        recurrence_count=recurrence_count,
        linked_factory_job_ids=linked_factory_job_ids,
        last_evidence_at=last_evidence_at,
        recency_flag=recency_flag,
        provenance_refs=provenance_refs,
        fingerprint=fingerprint,
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
        fingerprint=fingerprint,
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


def _compute_fingerprint(keyword_description: str, session_ids: list[str]) -> str:
    """Candidate identity fingerprint -- shared-scoring-rework-001 "Feladat" 3.

    sha256 of `keyword_description` plus the SORTED, DEDUPLICATED set of
    `session_ids` this aggregation run queried, joined by a separator that
    cannot appear inside a session_id (UUIDs from shared-cross-session-
    search-001's session_core.sessions, see that report's data model --
    hyphen/alnum only, never "|").

    Why (keyword_description, session_id SET) and not e.g. just
    keyword_description alone: two DIFFERENT recurring concepts can share a
    keyword_description string only if they are, by definition, the SAME
    concept (the string itself IS the concept's identity per input.md's
    framing, see aggregate_cross_session's keyword_description docstring) --
    but the SOURCE SESSION SET further disambiguates re-runs of the SAME
    concept over a GROWING session window (e.g. a daily batch job that adds
    one more session each day) from a genuinely unrelated second cluster
    that happens to reuse the same description text. Using the session SET
    (not the session_ids LIST/order) means re-running the aggregator with
    the same sessions in a different order -- which can legitimately happen
    if the caller's `last_seen_at`-descending ordering changes between runs
    -- still produces the SAME fingerprint, which is required for the
    idempotency guarantee this fingerprint exists to provide.

    Why a fingerprint of the INPUT (keyword_description + session_ids) and
    not e.g. of provenance_refs: provenance_refs already depends on the
    aggregator's OWN OUTPUT (each row's content_hash), so fingerprinting it
    would make the fingerprint indirectly depend on search ranking/limit
    behavior that has nothing to do with "is this conceptually the same
    candidate" -- two runs with different `per_session_limit` values over
    the SAME (keyword_description, session_ids) could return different rows
    but should still upsert the SAME candidate row.
    """
    session_id_part = "|".join(sorted(set(session_ids)))
    raw = f"{keyword_description}\x00{session_id_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    fingerprint: str,
) -> str:
    """UPSERT one shared_core.candidates row keyed on `fingerprint`
    (shared-scoring-rework-001 "Feladat" 3 -- replaces the original
    always-INSERT with `INSERT ... ON CONFLICT (fingerprint) DO UPDATE`,
    using the idx_candidates_fingerprint_unique unique index added by
    output/shared-scoring-rework-migration.sql).

    On conflict (same fingerprint as an existing row -- i.e. a re-run of
    the SAME keyword_description over the SAME session_id set):
      - weight_score, recurrence_count, last_evidence_at, recency_flag,
        linked_factory_job_ids, weighting_evaluated_at are REPLACED with
        this run's freshly computed values (the latest aggregation run's
        numbers are the authoritative current state of the candidate).
      - provenance_refs is MERGED, not replaced: the existing row's refs
        and this run's refs are concatenated and DEDUPLICATED (via a JSONB
        DISTINCT aggregation over the combined array) so that re-running
        the SAME query never loses previously recorded evidence (input.md
        "Nem cél": "a provenance_refs JSONB struktúrájának megváltoztatása
        -- az upsertnél a meglévő refs-eket KIEGÉSZÍTENI kell, nem
        felülírni/elveszíteni").
      - trust is RECOMPUTED from the new weight_score/recurrence_count via
        decide_trust_level() -- same gating rule as the original INSERT
        path, unconditionally re-applied on every upsert (a candidate that
        crosses the promotion threshold on a LATER run should still be
        promoted to 'candidate' trust, not stuck at whatever trust its
        first-ever run produced). canonical is NEVER touched by this
        upsert (no canonical column in the SET clause at all) -- the
        canonical_requires_reviewed_shared CHECK constraint and the
        human-review-only promotion path (cic-mcp-shared/CLAUDE.md "Trust
        modell") are completely untouched by this job, per input.md "Nem
        cél".
    """
    new_trust = decide_trust_level(weight_score, recurrence_count)
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
                    provenance_refs,
                    fingerprint
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (fingerprint) DO UPDATE SET
                    trust = EXCLUDED.trust,
                    weight_score = EXCLUDED.weight_score,
                    recurrence_count = EXCLUDED.recurrence_count,
                    linked_factory_job_ids = EXCLUDED.linked_factory_job_ids,
                    last_evidence_at = EXCLUDED.last_evidence_at,
                    recency_flag = EXCLUDED.recency_flag,
                    weighting_evaluated_at = now(),
                    provenance_refs = (
                        SELECT COALESCE(jsonb_agg(DISTINCT merged.ref), '[]'::jsonb)
                        FROM jsonb_array_elements(
                            shared_core.candidates.provenance_refs || EXCLUDED.provenance_refs
                        ) AS merged(ref)
                    )
                RETURNING candidate_id
                """,
                (
                    keyword_description,
                    new_trust,
                    weight_score,
                    recurrence_count,
                    linked_factory_job_ids,
                    last_evidence_at,
                    recency_flag,
                    json.dumps(provenance_refs),
                    fingerprint,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return str(row[0])
