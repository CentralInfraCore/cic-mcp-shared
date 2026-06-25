"""Operator-driven candidate review lifecycle: candidate/mixed ->
reviewed_shared -> canonical, or -> rejected/superseded.

Job: shared-candidate-review-lifecycle-001.

Context (input.md "Kontextus"): shared_core.candidates ALREADY enforces at
the DB level that canonical=TRUE is only possible when trust='reviewed_shared'
(candidates_canonical_requires_reviewed_shared CHECK constraint, shared-core-
storage-schema.sql:62-64). shared-promotion-candidate-logic-001 ALREADY
implemented the mixed -> candidate automatic transition (decide_trust_level()
in aggregator.py). What was MISSING (and what this module provides) is the
operator-callable tool that EXECUTES the candidate -> reviewed_shared (and
-> superseded/rejected) transition, with an audit trail -- previously this
decision could only be made via a manual, un-audited direct SQL UPDATE.

Four operator-callable functions, all explicit/human-invoked (input.md
"Nem cél": "BÁRMILYEN automatikus (nem-operátor-hívott) ... átmenet" is out
of scope -- there is no heuristic/automated caller anywhere in this module):

  - promote_to_reviewed_shared(candidate_id, actor, reason)
        candidate/mixed -> reviewed_shared. Does NOT set canonical.
  - promote_to_canonical(candidate_id, actor, reason)
        reviewed_shared -> canonical=TRUE. Validates trust=='reviewed_shared'
        ITSELF, BEFORE issuing the UPDATE -- this is a pre-flight check, not
        a bypass: the DB CHECK constraint
        (candidates_canonical_requires_reviewed_shared) remains the actual
        final enforcement layer and is never disabled, never raced around.
        If the tool's own pre-check is somehow wrong (e.g. a TOCTOU race
        with a concurrent transition), the DB constraint still rejects the
        UPDATE and this function surfaces that as ReviewLifecycleError.
  - reject_candidate(candidate_id, actor, reason)
        Marks the row as rejected from the review queue (to_trust='rejected'
        in the audit row). Does not delete/modify shared_core.candidates
        beyond updated_at -- a rejected candidate keeps its prior trust
        value (it simply will not be reviewed again without a new reason),
        the audit log is the durable record of the rejection decision.
  - mark_superseded(candidate_id, superseded_by_id, actor, reason)
        Sets shared_core.candidates.superseded_by/superseded_at/
        superseded_reviewed_by (columns that already existed in the schema,
        shared-core-storage-schema.sql:74-80, but had no operator-facing
        write path before this job).

Every function that performs a shared_core.candidates UPDATE writes the
corresponding shared_audit.candidate_transitions row (migrations/0001_
candidate_transitions_audit.sql) IN THE SAME TRANSACTION -- never as a
separate best-effort write, so the audit row and the data row cannot
diverge (no UPDATE without an audit row, no audit row without an UPDATE).

Rejected attempts -- i.e. ReviewLifecycleError raised BEFORE any UPDATE is
issued -- intentionally do NOT produce a shared_audit.candidate_transitions
row: the transaction is never opened/committed for those, so there is
nothing to audit-log about an action that never executed. See
output/shared-candidate-review-lifecycle.md "Findings" for the evidence
that this is a deliberate design choice, not an omission.

Not in scope (input.md "Nem cél"): the mixed -> candidate gating logic
(shared-promotion-candidate-logic-001, unmodified here), the weight_score/
recurrence_count scoring formula (shared-scoring-rework-001), and any
automatic (non-operator) reviewed_shared/canonical transition.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from shared_core.aggregator import SharedStoreConfig

# Trust values a candidate may be promoted FROM via promote_to_reviewed_shared()
# -- per input.md Feladat 2: "ellenőrzi, hogy a candidate JELENLEG
# trust IN ('candidate', 'mixed')-e".
_PROMOTABLE_FROM_TRUST = ("candidate", "mixed")

_REVIEWED_SHARED = "reviewed_shared"


class ReviewLifecycleError(Exception):
    """Raised when an operator-invoked review transition is rejected by this
    module's OWN pre-flight validation (not the DB) -- e.g. wrong current
    trust value, unknown candidate_id. Distinct from psycopg.errors.CheckViolation,
    which is what surfaces if code bypasses this module and the DB CHECK
    constraint itself rejects a raw UPDATE (see tests/test_shared_core/
    test_review_lifecycle.py::test_promote_to_canonical_db_constraint_rejects_bypass).
    """


@dataclass(frozen=True)
class CandidateRow:
    """Snapshot of the shared_core.candidates columns this module reads/
    validates against, returned by _fetch_candidate() so callers (and
    tests) can inspect the ACTUAL row state, not an assumed one.
    """

    candidate_id: str
    trust: str
    canonical: bool
    superseded_by: str | None


@dataclass(frozen=True)
class TransitionResult:
    """Everything produced by one transition call, returned so the caller
    (and tests) can inspect the actual written values rather than
    re-deriving them from the DB alone.
    """

    candidate_id: str
    transition_id: str
    from_trust: str
    to_trust: str
    from_canonical: bool
    to_canonical: bool
    actor: str
    reason: str


def _fetch_candidate(cur, candidate_id: str) -> CandidateRow:
    """Read the CURRENT shared_core.candidates row state inside the active
    transaction (so the validation below sees the live, not stale, value --
    no separate connection/snapshot).
    """
    cur.execute(
        "SELECT candidate_id, trust, canonical, superseded_by "
        "FROM shared_core.candidates WHERE candidate_id = %s",
        (candidate_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ReviewLifecycleError(f"no shared_core.candidates row found for candidate_id={candidate_id}")
    return CandidateRow(
        candidate_id=str(row[0]), trust=row[1], canonical=row[2], superseded_by=str(row[3]) if row[3] else None
    )


def _insert_transition_row(
    cur,
    *,
    candidate_id: str,
    from_trust: str,
    to_trust: str,
    from_canonical: bool,
    to_canonical: bool,
    actor: str,
    reason: str,
) -> str:
    """INSERT one shared_audit.candidate_transitions row -- ALWAYS called
    from inside the same cursor/transaction as the shared_core.candidates
    UPDATE it documents (see module docstring "Every function that performs
    ... UPDATE writes the corresponding ... row IN THE SAME TRANSACTION").
    """
    cur.execute(
        """
        INSERT INTO shared_audit.candidate_transitions (
            candidate_id, from_trust, to_trust,
            from_canonical, to_canonical, actor, reason
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING transition_id
        """,
        (candidate_id, from_trust, to_trust, from_canonical, to_canonical, actor, reason),
    )
    row = cur.fetchone()
    return str(row[0])


def promote_to_reviewed_shared(
    candidate_id: str,
    actor: str,
    reason: str,
    *,
    config: SharedStoreConfig | None = None,
) -> TransitionResult:
    """Promote a candidate from trust IN ('candidate', 'mixed') to
    'reviewed_shared'. Does NOT touch canonical (it stays whatever it was --
    which the schema's own DEFAULT FALSE and CHECK constraint guarantee is
    FALSE for any row that was not already 'reviewed_shared', since
    canonical=TRUE requires trust='reviewed_shared' already).

    If the candidate is ALREADY 'reviewed_shared', this is a no-op error
    (input.md Feladat 2: "ha már reviewed_shared, no-op vagy hiba,
    indokolva") -- raises ReviewLifecycleError rather than silently
    re-writing an identical row and audit entry, so a caller cannot
    accidentally produce a string of meaningless duplicate audit rows for
    an already-completed promotion.

    Raises:
        ReviewLifecycleError: candidate_id not found, OR current trust is
            not in ('candidate', 'mixed') (includes the already-
            reviewed_shared case).
    """
    config = config or SharedStoreConfig.from_env()
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor() as cur:
            current = _fetch_candidate(cur, candidate_id)
            if current.trust not in _PROMOTABLE_FROM_TRUST:
                raise ReviewLifecycleError(
                    f"candidate_id={candidate_id} has trust={current.trust!r}, "
                    f"expected one of {_PROMOTABLE_FROM_TRUST!r} -- "
                    "cannot promote_to_reviewed_shared() (already reviewed_shared, "
                    "or in an unexpected trust state)"
                )

            cur.execute(
                "UPDATE shared_core.candidates SET trust = %s, updated_at = now() "
                "WHERE candidate_id = %s",
                (_REVIEWED_SHARED, candidate_id),
            )

            transition_id = _insert_transition_row(
                cur,
                candidate_id=candidate_id,
                from_trust=current.trust,
                to_trust=_REVIEWED_SHARED,
                from_canonical=current.canonical,
                to_canonical=current.canonical,
                actor=actor,
                reason=reason,
            )
        conn.commit()

    return TransitionResult(
        candidate_id=candidate_id,
        transition_id=transition_id,
        from_trust=current.trust,
        to_trust=_REVIEWED_SHARED,
        from_canonical=current.canonical,
        to_canonical=current.canonical,
        actor=actor,
        reason=reason,
    )


def promote_to_canonical(
    candidate_id: str,
    actor: str,
    reason: str,
    *,
    config: SharedStoreConfig | None = None,
) -> TransitionResult:
    """Promote a candidate's canonical flag to TRUE. ONLY valid when the
    row's CURRENT trust is 'reviewed_shared'.

    This function validates trust=='reviewed_shared' ITSELF, in Python,
    BEFORE issuing the UPDATE (input.md Feladat 2: "a canonical beállítása
    ... a DB CHECK constraint-et MEGELŐZŐEN saját validációval is
    ellenőrzi"). This is a pre-flight check that gives a clear,
    application-level error message -- it does NOT replace or bypass the
    DB's candidates_canonical_requires_reviewed_shared CHECK constraint,
    which still runs on the actual UPDATE and remains the final
    enforcement layer (input.md: "ez a tool NEM bypassolja, csak előzetesen
    validál"). If this function's own pre-check were ever wrong (e.g. a
    concurrent transition raced in between _fetch_candidate() and the
    UPDATE), the UPDATE would still be rejected by the DB constraint and
    psycopg would raise psycopg.errors.CheckViolation, NOT silently
    succeed -- proven directly (without going through this function) in
    tests/test_shared_core/test_review_lifecycle.py::
    test_promote_to_canonical_db_constraint_rejects_bypass.

    Raises:
        ReviewLifecycleError: candidate_id not found, OR current trust is
            not 'reviewed_shared' (this module's own pre-flight rejection,
            no UPDATE issued, no audit row written).
    """
    config = config or SharedStoreConfig.from_env()
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor() as cur:
            current = _fetch_candidate(cur, candidate_id)
            if current.trust != _REVIEWED_SHARED:
                raise ReviewLifecycleError(
                    f"candidate_id={candidate_id} has trust={current.trust!r}, "
                    f"expected {_REVIEWED_SHARED!r} -- cannot promote_to_canonical() "
                    "(tool-level pre-flight validation rejected this BEFORE any UPDATE "
                    "was issued; the DB CHECK constraint candidates_canonical_requires_"
                    "reviewed_shared would reject it too, but this check runs first)"
                )
            if current.canonical:
                raise ReviewLifecycleError(
                    f"candidate_id={candidate_id} is already canonical=TRUE -- no-op, "
                    "not re-promoting (no UPDATE issued, no duplicate audit row)"
                )

            cur.execute(
                "UPDATE shared_core.candidates SET canonical = TRUE, updated_at = now() "
                "WHERE candidate_id = %s",
                (candidate_id,),
            )

            transition_id = _insert_transition_row(
                cur,
                candidate_id=candidate_id,
                from_trust=current.trust,
                to_trust=current.trust,
                from_canonical=False,
                to_canonical=True,
                actor=actor,
                reason=reason,
            )
        conn.commit()

    return TransitionResult(
        candidate_id=candidate_id,
        transition_id=transition_id,
        from_trust=current.trust,
        to_trust=current.trust,
        from_canonical=False,
        to_canonical=True,
        actor=actor,
        reason=reason,
    )


def reject_candidate(
    candidate_id: str,
    actor: str,
    reason: str,
    *,
    config: SharedStoreConfig | None = None,
) -> TransitionResult:
    """Record an operator's rejection of a candidate from the review queue.

    Does NOT modify shared_core.candidates.trust/canonical -- a rejection is
    a review-queue decision ("do not promote this"), not a retraction of
    the row's current (already DB-valid) trust state. The row's updated_at
    is still bumped, and the audit row (to_trust='rejected') is the durable
    record that an operator looked at this candidate and declined to
    promote it, with `reason` capturing why.

    Raises:
        ReviewLifecycleError: candidate_id not found.
    """
    config = config or SharedStoreConfig.from_env()
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor() as cur:
            current = _fetch_candidate(cur, candidate_id)

            cur.execute(
                "UPDATE shared_core.candidates SET updated_at = now() WHERE candidate_id = %s",
                (candidate_id,),
            )

            transition_id = _insert_transition_row(
                cur,
                candidate_id=candidate_id,
                from_trust=current.trust,
                to_trust="rejected",
                from_canonical=current.canonical,
                to_canonical=current.canonical,
                actor=actor,
                reason=reason,
            )
        conn.commit()

    return TransitionResult(
        candidate_id=candidate_id,
        transition_id=transition_id,
        from_trust=current.trust,
        to_trust="rejected",
        from_canonical=current.canonical,
        to_canonical=current.canonical,
        actor=actor,
        reason=reason,
    )


def mark_superseded(
    candidate_id: str,
    superseded_by_id: str,
    actor: str,
    reason: str,
    *,
    config: SharedStoreConfig | None = None,
) -> TransitionResult:
    """Mark `candidate_id` as superseded by `superseded_by_id`, writing the
    existing shared_core.candidates.superseded_by/superseded_at/
    superseded_reviewed_by columns (shared-core-storage-schema.sql:74-80 --
    these columns already existed; this is their first operator-facing
    write path).

    `superseded_by_id` must itself be an existing shared_core.candidates
    row (enforced by the schema's own
    candidates_superseded_by_fkey FK -- this function does not duplicate
    that check, the FK violation surfaces as psycopg.errors.ForeignKeyViolation
    if an unknown id is passed).

    Raises:
        ReviewLifecycleError: candidate_id not found.
    """
    config = config or SharedStoreConfig.from_env()
    with psycopg.connect(config.conninfo()) as conn:
        with conn.cursor() as cur:
            current = _fetch_candidate(cur, candidate_id)

            cur.execute(
                "UPDATE shared_core.candidates "
                "SET superseded_by = %s, superseded_at = now(), "
                "    superseded_reviewed_by = %s, updated_at = now() "
                "WHERE candidate_id = %s",
                (superseded_by_id, actor, candidate_id),
            )

            transition_id = _insert_transition_row(
                cur,
                candidate_id=candidate_id,
                from_trust=current.trust,
                to_trust="superseded",
                from_canonical=current.canonical,
                to_canonical=current.canonical,
                actor=actor,
                reason=reason,
            )
        conn.commit()

    return TransitionResult(
        candidate_id=candidate_id,
        transition_id=transition_id,
        from_trust=current.trust,
        to_trust="superseded",
        from_canonical=current.canonical,
        to_canonical=current.canonical,
        actor=actor,
        reason=reason,
    )
