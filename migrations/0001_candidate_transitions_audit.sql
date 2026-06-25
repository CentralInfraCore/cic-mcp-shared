-- ============================================================================
-- shared-candidate-review-lifecycle-001
-- PostgreSQL migration for cic-mcp-shared — shared_audit.candidate_transitions
--
-- STATUS: candidate — executed and proven against a real running Postgres
-- instance (postgres:16-alpine, see output/shared-candidate-review-
-- lifecycle.md "Real Postgres Proof" for the actual psql/psycopg output).
--
-- Depends on shared_core.candidates already existing (output/shared-core-
-- storage-schema.sql, shared-core-storage-implementation-001), specifically
-- the candidate_id PRIMARY KEY this table's FK references.
--
-- Purpose: an append-only audit trail for every operator-driven trust/
-- canonical transition on a shared_core.candidates row -- candidate/mixed ->
-- reviewed_shared -> canonical, or -> rejected/superseded. This table is
-- written EXCLUSIVELY by shared_core/review_lifecycle.py's
-- promote_to_reviewed_shared() / promote_to_canonical() / reject_candidate()
-- / mark_superseded() functions, inside the SAME transaction as the
-- shared_core.candidates UPDATE -- never as a separate, best-effort write
-- (see review_lifecycle.py for the actual transaction boundary).
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS shared_audit;

-- ============================================================================
-- TABLE: shared_audit.candidate_transitions
-- One row per operator-invoked trust/canonical transition attempt that
-- ACTUALLY EXECUTED (i.e. the shared_core.candidates row was updated in the
-- same transaction). Rejected attempts (tool-level validation failure, or a
-- hypothetical DB CHECK constraint rejection) are NOT written here -- see
-- review_lifecycle.py docstrings for why a rejected attempt has no row by
-- design (it never reached the UPDATE), and output/shared-candidate-review-
-- lifecycle.md "Findings" for how the rejected-attempt evidence is captured
-- without a misleading audit row.
-- ============================================================================

CREATE TABLE shared_audit.candidate_transitions (
    transition_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    candidate_id            UUID NOT NULL
        CONSTRAINT candidate_transitions_candidate_id_fkey
        REFERENCES shared_core.candidates (candidate_id)
        ON DELETE CASCADE,

    from_trust              TEXT NOT NULL
        CONSTRAINT candidate_transitions_from_trust_valid_values
        CHECK (from_trust IN ('mixed', 'candidate', 'reviewed_shared')),

    to_trust                TEXT NOT NULL
        CONSTRAINT candidate_transitions_to_trust_valid_values
        CHECK (to_trust IN ('mixed', 'candidate', 'reviewed_shared', 'rejected', 'superseded')),

    from_canonical          BOOLEAN NOT NULL,
    to_canonical            BOOLEAN NOT NULL,

    -- actor: operator identifier string (e.g. a username/handle), NEVER
    -- NULL -- every transition is explicit and operator-attributed, per
    -- input.md "Nem cél": "BÁRMILYEN automatikus (nem-operátor-hívott)
    -- ... átmenet" is out of scope, so this column has no automation
    -- default value.
    actor                   TEXT NOT NULL,

    reason                  TEXT NOT NULL,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX idx_candidate_transitions_candidate_id
    ON shared_audit.candidate_transitions (candidate_id);

CREATE INDEX idx_candidate_transitions_created_at
    ON shared_audit.candidate_transitions (created_at);

-- ============================================================================
-- Comments (documentation embedded in the schema itself)
-- ============================================================================

COMMENT ON SCHEMA shared_audit IS
    'Audit trail schema for cic-mcp-shared operator-driven review/promotion actions. Separate from shared_core so candidate data and its audit trail have independent lifecycle/retention policies.';

COMMENT ON TABLE shared_audit.candidate_transitions IS
    'One row per EXECUTED operator-invoked trust/canonical transition on a shared_core.candidates row, written in the same transaction as the UPDATE. See shared_core/review_lifecycle.py. Rejected attempts (tool validation or DB CHECK constraint) intentionally have NO row here.';

COMMENT ON COLUMN shared_audit.candidate_transitions.actor IS
    'Operator identifier string. NEVER set by automated/heuristic code paths -- every row here corresponds to an explicit, human-invoked promote_to_reviewed_shared()/promote_to_canonical()/reject_candidate()/mark_superseded() call.';

COMMENT ON COLUMN shared_audit.candidate_transitions.to_trust IS
    'Target trust value, OR the sentinel values rejected/superseded for reject_candidate()/mark_superseded() calls (these do not change shared_core.candidates.trust itself, but ARE operator-invoked lifecycle decisions worth auditing identically).';
