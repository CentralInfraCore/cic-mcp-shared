-- ============================================================================
-- shared-scoring-rework-001
-- ADDITIVE migration on top of output/shared-core-storage-schema.sql.
-- STATUS: candidate -- applied and verified against a real Postgres
-- instance (pgvector/pgvector:pg16, see output/shared-scoring-rework.md for
-- the actual psql/pytest output that proves idempotency and the score-cap
-- effect, not merely the column's presence).
-- This file does NOT replace or rewrite output/shared-core-storage-
-- schema.sql. It is applied SECOND, after that file, against the same
-- instance -- backward-compatible: existing rows are NOT touched/dropped,
-- the new column is added with a computed backfill for any pre-existing
-- rows (none are expected in a fresh-from-this-job environment, but the
-- backfill keeps this migration safe to run against an environment that
-- already has shared_core.candidates rows from a prior aggregator run).
--
-- One change: a single new column, `fingerprint`, plus the UNIQUE
-- constraint that makes `INSERT ... ON CONFLICT (fingerprint) DO UPDATE`
-- (shared_core/aggregator.py:_insert_candidate, see that function's
-- docstring for the exact fingerprint definition) an idempotent upsert
-- instead of an always-INSERT.
-- ============================================================================

ALTER TABLE shared_core.candidates
    ADD COLUMN IF NOT EXISTS fingerprint TEXT NULL;

COMMENT ON COLUMN shared_core.candidates.fingerprint IS
    'Stable identity hash for one (keyword_description, source session_id set) pair -- sha256 of keyword_description plus the SORTED, DEDUPLICATED set of session_id values present in provenance_refs at aggregation time (see shared_core/aggregator.py:_compute_fingerprint). Two aggregation runs over the SAME keyword_description and the SAME session_id set produce the SAME fingerprint, which is what makes the ON CONFLICT (fingerprint) DO UPDATE upsert idempotent. NULL is allowed only for rows inserted before this migration (pre-existing data is not backfilled with a fabricated fingerprint, since this migration cannot know which session_ids a pre-existing row TRULY originated from beyond what is already in provenance_refs -- see shared-scoring-rework.md "Decisions Proposed" for why a NULL-tolerant backfill, not a fabricated one, was chosen).';

-- A NULL fingerprint must never silently collide with another NULL
-- fingerprint under a plain UNIQUE constraint (Postgres treats NULL <>
-- NULL, so two NULL rows would already not collide) -- but to make the
-- ON CONFLICT (fingerprint) target valid, the column needs a unique index.
-- A plain UNIQUE constraint over a nullable column is exactly what is
-- needed here: Postgres allows multiple NULLs under UNIQUE (NULLs are
-- never considered equal to each other), so legacy pre-migration rows
-- (fingerprint IS NULL) are unaffected, while every NEW row written by the
-- reworked aggregator always supplies a non-NULL fingerprint and therefore
-- participates in the uniqueness/upsert guarantee.
CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_fingerprint_unique
    ON shared_core.candidates (fingerprint);
