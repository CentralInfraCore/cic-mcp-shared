"""Real-Postgres test for shared_core.review_lifecycle.

Job: shared-candidate-review-lifecycle-001, "Feladat" 3 ("Valós, futtatott
bizonyíték").

Requires a REACHABLE Postgres instance with:
  - shared_core.candidates already applied (output/shared-core-storage-
    schema.sql, shared-core-storage-implementation-001)
  - shared_audit.candidate_transitions already applied (migrations/0001_
    candidate_transitions_audit.sql, THIS job)

Same "do not silently skip the real-evidence test" stance as
tests/test_shared_core/test_aggregator.py -- if Postgres is unreachable or
the schemas are missing, these tests fail loudly (pytest.fail), they do not
skip.

Covers BOTH halves of input.md Feladat 3:
  1. ONE full valid transition path: mixed/candidate -> reviewed_shared ->
     canonical, re-reading the ACTUAL row state after every step, plus the
     ACTUAL shared_audit.candidate_transitions rows for every step.
  2. ONE invalid attempt: promote_to_canonical() on a trust='candidate' row
     -- rejected by the tool's OWN validation (ReviewLifecycleError, no
     UPDATE issued) AND (separately, bypassing the tool entirely with a raw
     SQL UPDATE) rejected by the DB CHECK constraint
     (candidates_canonical_requires_reviewed_shared) -- proving the DB
     constraint is still the real final enforcement layer, not merely
     documented.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from shared_core.aggregator import SharedStoreConfig
from shared_core.review_lifecycle import (
    ReviewLifecycleError,
    mark_superseded,
    promote_to_canonical,
    promote_to_reviewed_shared,
    reject_candidate,
)


def _pg_config() -> SharedStoreConfig:
    cfg = SharedStoreConfig(
        host=os.environ.get("SESSION_STORE_PG_HOST", "localhost"),
        port=int(os.environ.get("SESSION_STORE_PG_PORT", "55436")),
        dbname=os.environ.get("SESSION_STORE_PG_DB", "testdb"),
        user=os.environ.get("SESSION_STORE_PG_USER", "postgres"),
        password=os.environ.get("SESSION_STORE_PG_PASSWORD", "test"),
    )
    try:
        with psycopg.connect(cfg.conninfo(), connect_timeout=5):
            pass
    except psycopg.OperationalError as exc:
        pytest.fail(
            "Cannot reach a real Postgres instance for the review_lifecycle "
            f"tests. Original error: {exc}"
        )
    return cfg


@pytest.fixture(scope="module")
def pg_config() -> SharedStoreConfig:
    return _pg_config()


def _insert_raw_candidate(pg_config: SharedStoreConfig, *, trust: str) -> str:
    """Insert ONE shared_core.candidates row directly (no aggregator
    involved -- this test module exercises review_lifecycle.py in
    isolation, the aggregator's own INSERT path is covered by
    test_aggregator.py), and return its candidate_id.
    """
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shared_core.candidates (keyword_description, trust) "
                "VALUES (%s, %s) RETURNING candidate_id",
                (f"review-lifecycle-pytest-{uuid.uuid4().hex[:8]}", trust),
            )
            row = cur.fetchone()
        conn.commit()
    return str(row[0])


def _fetch_row(pg_config: SharedStoreConfig, candidate_id: str) -> tuple:
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trust, canonical FROM shared_core.candidates WHERE candidate_id = %s",
                (candidate_id,),
            )
            return cur.fetchone()


def _fetch_transition_rows(pg_config: SharedStoreConfig, candidate_id: str) -> list[tuple]:
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT from_trust, to_trust, from_canonical, to_canonical, actor, reason "
                "FROM shared_audit.candidate_transitions "
                "WHERE candidate_id = %s ORDER BY created_at ASC",
                (candidate_id,),
            )
            return cur.fetchall()


# ============================================================================
# 1. Full valid transition path: candidate -> reviewed_shared -> canonical
# ============================================================================


def test_full_valid_transition_path_candidate_to_canonical(pg_config):
    candidate_id = _insert_raw_candidate(pg_config, trust="candidate")

    # --- step 1: candidate -> reviewed_shared -------------------------
    result_1 = promote_to_reviewed_shared(
        candidate_id, actor="operator-alice", reason="recurring concept confirmed manually", config=pg_config
    )
    assert result_1.from_trust == "candidate"
    assert result_1.to_trust == "reviewed_shared"
    assert result_1.to_canonical is False

    trust_after_1, canonical_after_1 = _fetch_row(pg_config, candidate_id)
    assert trust_after_1 == "reviewed_shared", f"expected reviewed_shared after step 1, got {trust_after_1!r}"
    assert canonical_after_1 is False

    # --- step 2: reviewed_shared -> canonical --------------------------
    result_2 = promote_to_canonical(
        candidate_id, actor="operator-alice", reason="cross-checked against two independent sources", config=pg_config
    )
    assert result_2.from_trust == "reviewed_shared"
    assert result_2.to_canonical is True

    trust_after_2, canonical_after_2 = _fetch_row(pg_config, candidate_id)
    assert trust_after_2 == "reviewed_shared", f"trust must stay reviewed_shared, got {trust_after_2!r}"
    assert canonical_after_2 is True, "canonical must be TRUE after promote_to_canonical()"

    # --- audit log: both steps present, in order, correct content ------
    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert len(rows) == 2, f"expected exactly 2 audit rows for the 2 executed transitions, got {len(rows)}"

    step1_row, step2_row = rows
    assert step1_row[:4] == ("candidate", "reviewed_shared", False, False)
    assert step1_row[4] == "operator-alice"
    assert "recurring concept" in step1_row[5]

    assert step2_row[:4] == ("reviewed_shared", "reviewed_shared", False, True)
    assert step2_row[4] == "operator-alice"
    assert "cross-checked" in step2_row[5]


def test_full_valid_transition_path_starting_from_mixed(pg_config):
    """Same path, but starting from trust='mixed' -- input.md Feladat 2
    explicitly requires promote_to_reviewed_shared() to accept BOTH
    'candidate' and 'mixed' as the starting trust value.
    """
    candidate_id = _insert_raw_candidate(pg_config, trust="mixed")

    result = promote_to_reviewed_shared(
        candidate_id, actor="operator-bob", reason="manual override, recurrence too low but content verified", config=pg_config
    )
    assert result.from_trust == "mixed"
    assert result.to_trust == "reviewed_shared"

    trust_after, _ = _fetch_row(pg_config, candidate_id)
    assert trust_after == "reviewed_shared"

    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert len(rows) == 1
    assert rows[0][:2] == ("mixed", "reviewed_shared")


# ============================================================================
# 2. Invalid attempt: promote_to_canonical() on trust='candidate'
# ============================================================================


def test_promote_to_canonical_rejected_by_tool_validation(pg_config):
    """trust='candidate' (NOT reviewed_shared) -- promote_to_canonical()
    must reject this via its OWN pre-flight validation, BEFORE issuing any
    UPDATE, and must NOT write an audit row for the rejected attempt.
    """
    candidate_id = _insert_raw_candidate(pg_config, trust="candidate")

    with pytest.raises(ReviewLifecycleError, match="expected 'reviewed_shared'"):
        promote_to_canonical(candidate_id, actor="operator-eve", reason="attempting to skip review", config=pg_config)

    # row must be UNCHANGED -- no UPDATE was issued
    trust_after, canonical_after = _fetch_row(pg_config, candidate_id)
    assert trust_after == "candidate", "trust must be unchanged after a rejected attempt"
    assert canonical_after is False, "canonical must still be FALSE after a rejected attempt"

    # no audit row for a rejected (never-executed) attempt
    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert rows == [], (
        "a tool-level-rejected attempt must NOT produce a "
        "shared_audit.candidate_transitions row (no UPDATE was ever issued)"
    )


def test_promote_to_canonical_db_constraint_rejects_bypass(pg_config):
    """Separately from the tool's own validation: if code BYPASSES
    review_lifecycle.py entirely and issues a raw SQL UPDATE setting
    canonical=TRUE on a trust='candidate' row, the DB's OWN CHECK
    constraint (candidates_canonical_requires_reviewed_shared,
    output/shared-core-storage-schema.sql:62-64) must reject it. This
    proves the DB constraint is the actual final enforcement layer, not
    merely documented -- this test does not call review_lifecycle.py at
    all.
    """
    candidate_id = _insert_raw_candidate(pg_config, trust="candidate")

    with pytest.raises(psycopg.errors.CheckViolation) as exc_info:
        with psycopg.connect(pg_config.conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE shared_core.candidates SET canonical = TRUE WHERE candidate_id = %s",
                    (candidate_id,),
                )
            conn.commit()

    assert "candidates_canonical_requires_reviewed_shared" in str(exc_info.value)

    # row must be UNCHANGED -- the failed transaction did not commit
    trust_after, canonical_after = _fetch_row(pg_config, candidate_id)
    assert trust_after == "candidate"
    assert canonical_after is False, "DB constraint must have rejected the raw bypass UPDATE"

    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert rows == [], "a DB-rejected raw bypass attempt must NOT produce an audit row either"


def test_promote_to_reviewed_shared_rejects_already_reviewed_shared(pg_config):
    """input.md Feladat 2: 'ha már reviewed_shared, no-op vagy hiba,
    indokolva' -- this module chooses 'hiba' (error), proven here.
    """
    candidate_id = _insert_raw_candidate(pg_config, trust="candidate")
    promote_to_reviewed_shared(candidate_id, actor="operator-carl", reason="first promotion", config=pg_config)

    with pytest.raises(ReviewLifecycleError, match="cannot promote_to_reviewed_shared"):
        promote_to_reviewed_shared(candidate_id, actor="operator-carl", reason="duplicate attempt", config=pg_config)

    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert len(rows) == 1, "the duplicate (rejected) attempt must not add a second audit row"


# ============================================================================
# reject_candidate() / mark_superseded()
# ============================================================================


def test_reject_candidate_writes_audit_row_without_changing_trust(pg_config):
    candidate_id = _insert_raw_candidate(pg_config, trust="candidate")

    result = reject_candidate(
        candidate_id, actor="operator-dana", reason="duplicate of an existing canonical fact", config=pg_config
    )
    assert result.to_trust == "rejected"

    trust_after, canonical_after = _fetch_row(pg_config, candidate_id)
    assert trust_after == "candidate", "reject_candidate() must not change the row's trust value"
    assert canonical_after is False

    rows = _fetch_transition_rows(pg_config, candidate_id)
    assert len(rows) == 1
    assert rows[0][1] == "rejected"
    assert rows[0][4] == "operator-dana"


def test_mark_superseded_writes_fk_columns_and_audit_row(pg_config):
    superseding_id = _insert_raw_candidate(pg_config, trust="candidate")
    superseded_id = _insert_raw_candidate(pg_config, trust="candidate")

    result = mark_superseded(
        superseded_id,
        superseding_id,
        actor="operator-frank",
        reason="newer candidate covers the same concept with more evidence",
        config=pg_config,
    )
    assert result.to_trust == "superseded"

    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT superseded_by, superseded_reviewed_by FROM shared_core.candidates "
                "WHERE candidate_id = %s",
                (superseded_id,),
            )
            superseded_by, superseded_reviewed_by = cur.fetchone()

    assert str(superseded_by) == superseding_id
    assert superseded_reviewed_by == "operator-frank"

    rows = _fetch_transition_rows(pg_config, superseded_id)
    assert len(rows) == 1
    assert rows[0][1] == "superseded"


def test_promote_to_reviewed_shared_unknown_candidate_id_raises(pg_config):
    with pytest.raises(ReviewLifecycleError, match="no shared_core.candidates row found"):
        promote_to_reviewed_shared(str(uuid.uuid4()), actor="operator-gail", reason="typo'd id", config=pg_config)
