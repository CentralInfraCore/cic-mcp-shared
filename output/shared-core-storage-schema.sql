-- ============================================================================
-- shared-core-storage-implementation-001
-- PostgreSQL schema for cic-mcp-shared — shared_core.candidates
--
-- STATUS: candidate — executed and proven against a real running Postgres
-- instance (postgres:16-alpine, see output/shared-core-storage-implementation.md
-- "Canonical Constraint - Real Postgres Proof" / "Conflicting/Superseded
-- Self-Reference Proof" for the actual psql output that proves the
-- constraints below, not merely their text).
--
-- Source of truth for field provenance (every column traced 1:1, no field
-- renamed/dropped without justification — see output/shared-core-storage-
-- implementation.md "Schema Design - Field-By-Field Traceability"):
--   jobs/shared-session-catalog-consumer-001/output/shared-session-catalog-
--     consumer.md (lines 254-255)         -> trust, canonical
--   jobs/shared-cross-session-search-001/output/shared-cross-session-
--     search.md (lines 368-376)            -> candidate_id, keyword_description,
--                                              provenance_refs, conflicting_with,
--                                              superseded_by, superseded_at,
--                                              superseded_reviewed_by
--   jobs/shared-weighting-model-001/output/shared-weighting-model.md
--     (lines 317-322)                       -> weight_score, recurrence_count,
--                                              linked_factory_job_ids,
--                                              last_evidence_at, recency_flag,
--                                              weighting_evaluated_at
--
-- Trust model enforced here (cic-mcp-shared/CLAUDE.md "Trust modell"):
--   trust: mixed / candidate / reviewed_shared
--   canonical: false by default, and NEVER true unless trust = 'reviewed_shared'.
--   The shared layer never produces a canonical fact automatically -- knowledge
--   promotion is a separate, human review flow, not this layer's job. This file
--   enforces that boundary at the DB level (see CHECK constraint below), it does
--   not just document it.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() for candidate_id default

CREATE SCHEMA IF NOT EXISTS shared_core;

-- ============================================================================
-- TABLE: shared_core.candidates
-- One row per shared-layer candidate record (cross-session aggregated
-- concept/cluster), as defined across the three prerequisite design reports.
-- ============================================================================

CREATE TABLE shared_core.candidates (
    -- --- shared-session-catalog-consumer-001 / shared-cross-session-search-001 ---
    candidate_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    keyword_description     TEXT NOT NULL,

    trust                   TEXT NOT NULL
        CONSTRAINT candidates_trust_valid_values
        CHECK (trust IN ('mixed', 'candidate', 'reviewed_shared')),

    -- canonical: DEFAULT false, and a CHECK constraint that makes it
    -- impossible for canonical=true to be stored unless trust='reviewed_shared'
    -- already holds on the SAME row. This is the single most load-bearing
    -- constraint in this file -- see output/shared-core-storage-
    -- implementation.md "Canonical Constraint - Real Postgres Proof" for the
    -- actual rejected INSERT/UPDATE that proves this, not just its presence.
    canonical               BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT candidates_canonical_requires_reviewed_shared
        CHECK (canonical = FALSE OR trust = 'reviewed_shared'),

    -- conflicting_with: nullable list of candidate_id references (symmetric
    -- many-to-many marker, NOT a foreign key -- see rationale below).
    conflicting_with        UUID[] NULL,

    -- superseded_by: nullable single self-reference. A real FK is used here
    -- (unlike conflicting_with) because it is a single scalar reference, so a
    -- normal FK constraint with ON DELETE SET NULL is both possible and
    -- useful (no dangling pointer if the superseding row is ever removed).
    superseded_by           UUID NULL
        CONSTRAINT candidates_superseded_by_fkey
        REFERENCES shared_core.candidates (candidate_id)
        ON DELETE SET NULL,

    superseded_at           TIMESTAMPTZ NULL,
    superseded_reviewed_by  TEXT NULL,

    -- --- shared-weighting-model-001 ---
    weight_score            DOUBLE PRECISION NOT NULL DEFAULT 0,
    recurrence_count        INTEGER NOT NULL DEFAULT 0
        CONSTRAINT candidates_recurrence_count_nonneg CHECK (recurrence_count >= 0),

    linked_factory_job_ids  TEXT[] NOT NULL DEFAULT '{}',

    last_evidence_at        TIMESTAMPTZ NULL,
    recency_flag            BOOLEAN NOT NULL DEFAULT FALSE,
    weighting_evaluated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- provenance_refs: list of {session_id, chunk_id, turn_id, content_hash}
    -- structures (shared-cross-session-search.md line 372 -- this is the
    -- ACTUAL structure in the source report; input.md's task description
    -- paraphrased it as {content_hash, ref_kind, ref_value}, see "Decisions
    -- Proposed" in the report for why the source report's literal structure
    -- was used instead of the paraphrase). Modeled as JSONB, not a separate
    -- table: each element is an immutable append-only pointer (never
    -- updated/queried by its own sub-fields in any consumer described in the
    -- three prerequisite reports), so a relational join table would add
    -- write/read overhead with no present benefit. JSONB also matches the
    -- "NEM a text tartalom, csak pointerek" (pointers only, not text content)
    -- framing -- this is metadata, not query-critical relational data.
    provenance_refs         JSONB NOT NULL DEFAULT '[]'::jsonb,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- conflicting_with is queried via "does candidate X appear in any other row's
-- conflicting_with array" -- GIN supports that containment/overlap query.
CREATE INDEX idx_candidates_conflicting_with
    ON shared_core.candidates USING GIN (conflicting_with);

CREATE INDEX idx_candidates_superseded_by
    ON shared_core.candidates (superseded_by);

CREATE INDEX idx_candidates_trust
    ON shared_core.candidates (trust);

CREATE INDEX idx_candidates_canonical
    ON shared_core.candidates (canonical)
    WHERE canonical = TRUE;

CREATE INDEX idx_candidates_provenance_refs
    ON shared_core.candidates USING GIN (provenance_refs);

-- ============================================================================
-- Comments (documentation embedded in the schema itself)
-- ============================================================================

COMMENT ON SCHEMA shared_core IS
    'cic-mcp-shared candidate-record storage (architecture.md "Schema szeparacio": cross-session clusters, summaries, candidate memories, conflicts).';

COMMENT ON TABLE shared_core.candidates IS
    'Cross-session aggregated candidate record. Fields traced 1:1 to shared-session-catalog-consumer-001, shared-cross-session-search-001, shared-weighting-model-001 design reports. See output/shared-core-storage-implementation.md.';

COMMENT ON COLUMN shared_core.candidates.canonical IS
    'MUST stay false unless trust=reviewed_shared (see candidates_canonical_requires_reviewed_shared CHECK below). Promotion to the knowledge layer is a separate human review flow, never automatic from weight_score or any other heuristic.';

COMMENT ON COLUMN shared_core.candidates.conflicting_with IS
    'Symmetric, non-authoritative list of candidate_id values this row conflicts with. Not a FK (array of references, Postgres cannot FK-constrain array elements without a trigger) -- detection logic is out of scope for this job, see Next Jobs.';

COMMENT ON COLUMN shared_core.candidates.superseded_by IS
    'Single newer candidate_id that superseded this row. Heuristic auto-assignment is allowed at trust<=candidate; promotion of the superseding row to reviewed_shared/canonical always requires human review (cic-mcp-shared/CLAUDE.md Trust modell).';

COMMENT ON COLUMN shared_core.candidates.provenance_refs IS
    'JSONB array of {session_id, chunk_id, turn_id, content_hash} pointers (shared-cross-session-search.md line 372). Pointers only, never persisted chunk text.';
