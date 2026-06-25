"""End-to-end tests for the shared-scoring-rework-001 fixes to
shared_core.aggregator: the per-session score CAP (replacing the original
sum-of-sums), the minimum-evidence-count gate, and the fingerprint-keyed
idempotent ON CONFLICT upsert.

Job: shared-scoring-rework-001, "Feladat" 4 ("Valós, futtatott bizonyíték —
MINDKÉT javítás").

Same evidence bar as tests/test_shared_core/test_aggregator.py: real
cic-mcp-session ingest pipeline (insert_envelope -> run_projection_batch ->
run_indexing_batch), real aggregate_cross_session() call (real MCP
subprocess via mcp.client.stdio), real psycopg follow-up SELECTs against
shared_core.candidates. ALL session fixture content is SYNTHETIC/FABRICATED
(input.md "Forbidden Shortcuts").

Requires the SAME environment as test_aggregator.py:
  - SHARED_AGGREGATOR_TEST_SESSION_REPO env var pointing at a
    cic-mcp-session checkout with .venv-host/bin/python already built.
  - a reachable Postgres instance with cic-mcp-session's schema/migration
    files AND output/shared-core-storage-schema.sql AND
    output/shared-scoring-rework-migration.sql (the fingerprint column +
    unique index) already applied.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from shared_core.aggregator import (
    MIN_PROVENANCE_REFS_FOR_CANDIDATE,
    SharedStoreConfig,
    _combine_session_scores,
    _min_max_normalize,
    aggregate_cross_session,
)

SHARED_REPO_ROOT = Path(__file__).resolve().parents[2]


def _session_repo_root() -> Path:
    raw = os.environ.get("SHARED_AGGREGATOR_TEST_SESSION_REPO")
    if not raw:
        pytest.fail(
            "SHARED_AGGREGATOR_TEST_SESSION_REPO is not set -- see "
            "test_aggregator.py module docstring for setup."
        )
    path = Path(raw).resolve()
    if not (path / "session_store").is_dir():
        pytest.fail(f"{path} does not look like a cic-mcp-session checkout (no session_store/)")
    return path


@pytest.fixture(scope="module")
def session_repo_root() -> Path:
    return _session_repo_root()


@pytest.fixture(scope="module", autouse=True)
def _add_session_repo_to_path(session_repo_root: Path):
    sys.path.insert(0, str(session_repo_root))
    sys.path.insert(0, str(SHARED_REPO_ROOT))
    yield
    sys.path.remove(str(session_repo_root))
    sys.path.remove(str(SHARED_REPO_ROOT))


@pytest.fixture(scope="module")
def pg_config(_add_session_repo_to_path):
    from session_store.envelope_writer import SessionStoreConfig

    cfg = SessionStoreConfig(
        host=os.environ.get("SESSION_STORE_PG_HOST", "localhost"),
        port=int(os.environ.get("SESSION_STORE_PG_PORT", "55440")),
        dbname=os.environ.get("SESSION_STORE_PG_DB", "testdb"),
        user=os.environ.get("SESSION_STORE_PG_USER", "postgres"),
        password=os.environ.get("SESSION_STORE_PG_PASSWORD", "test"),
    )
    try:
        with psycopg.connect(cfg.conninfo(), connect_timeout=5):
            pass
    except psycopg.OperationalError as exc:
        pytest.fail(f"Cannot reach a real Postgres instance. Original error: {exc}")
    os.environ["SESSION_STORE_PG_HOST"] = cfg.host
    os.environ["SESSION_STORE_PG_PORT"] = str(cfg.port)
    os.environ["SESSION_STORE_PG_DB"] = cfg.dbname
    os.environ["SESSION_STORE_PG_USER"] = cfg.user
    os.environ["SESSION_STORE_PG_PASSWORD"] = cfg.password
    return cfg


def _valid_envelope(**overrides) -> dict:
    base = {
        "apiVersion": "cic.session/v1",
        "kind": "SessionIngressEnvelope",
        "event_id": str(uuid.uuid4()),
        "provider": "claude-code",
        "provider_session_id": "shared-scoring-rework-pytest-session",
        "provider_event_name": "Stop",
        "source": {"kind": "hook", "collector": "log-event.py"},
        "occurred_at": datetime(2026, 6, 25, 13, 0, 0, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 6, 25, 13, 0, 1, tzinfo=timezone.utc),
        "payload": {"raw_text": "hello world"},
        "payload_encoding": "json",
        "raw_payload_hash": "sha256:" + ("a" * 64),
        "trust": "session_local",
        "canonical": False,
        "interpreted": False,
        "idempotency_key": "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
        "workstream": None,
        "schema_notes": None,
    }
    base.update(overrides)
    return base


def _seed_session(pg_config, *, turns: list[str]) -> str:
    from session_store.chunk_indexer import run_indexing_batch
    from session_store.envelope_writer import insert_envelope
    from session_store.turn_projector import run_projection_batch

    provider_session_id = f"shared-scoring-rework-pytest-{uuid.uuid4().hex[:8]}"
    base_time = datetime(2026, 6, 25, 13, 0, 0, tzinfo=timezone.utc)
    for i, text in enumerate(turns):
        envelope = _valid_envelope(
            event_id=str(uuid.uuid4()),
            provider_session_id=provider_session_id,
            provider_event_name="UserPromptSubmit" if i % 2 == 0 else "Stop",
            occurred_at=base_time + timedelta(minutes=i),
            ingested_at=base_time + timedelta(minutes=i, seconds=1),
            payload={"raw_text": text},
            idempotency_key="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
        )
        insert_envelope(envelope, config=pg_config)
        run_projection_batch(config=pg_config)
        run_indexing_batch(config=pg_config)

    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id FROM session_core.sessions WHERE provider_session_id = %s",
                (provider_session_id,),
            )
            row = cur.fetchone()
            assert row is not None, "real pipeline did not produce a session_core.sessions row"
            return str(row[0])


def _candidate_count_for_fingerprint(pg_config, fingerprint: str) -> int:
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM shared_core.candidates WHERE fingerprint = %s",
                (fingerprint,),
            )
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# 1. Pre-change evidence (quoted in output/shared-scoring-rework.md, run
#    here too so it stays a re-runnable check against the committed HEAD
#    via git, not just a one-time manual grep).
# ---------------------------------------------------------------------------
def test_pre_change_no_on_conflict_in_committed_head():
    import subprocess

    result = subprocess.run(
        ["git", "show", "HEAD:shared_core/aggregator.py"],
        cwd=SHARED_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ON CONFLICT" not in result.stdout, (
        "expected the committed (pre-this-job) aggregator.py to have NO "
        "ON CONFLICT clause -- if this fails, HEAD already includes this "
        "job's own upsert change, re-run against the actual pre-change commit."
    )


# ---------------------------------------------------------------------------
# 2. Score-cap unit-level proof: OLD formula (sum) vs NEW formula
#    (_combine_session_scores) on the SAME synthetic normalized-value
#    fixture, where one "session" has many matches and two others have one
#    strong match each.
# ---------------------------------------------------------------------------
def test_score_cap_one_busy_session_no_longer_dominates():
    # Session A: 6 weak-to-moderate matches (a "noisy" session with many
    # hits, none individually as strong as B/C's single best match).
    session_a_raw_scores = [0.50, 0.45, 0.40, 0.35, 0.30, 0.25]
    # Session B, C: exactly one very strong match each.
    session_b_raw_scores = [0.95]
    session_c_raw_scores = [0.92]

    normalized_a = _min_max_normalize(session_a_raw_scores)
    normalized_b = _min_max_normalize(session_b_raw_scores)
    normalized_c = _min_max_normalize(session_c_raw_scores)

    # OLD formula: sum(sum(normalized)) -- the bug input.md "Kontextus" describes.
    old_score = sum(normalized_a) + sum(normalized_b) + sum(normalized_c)

    # NEW formula: sum(_combine_session_scores(normalized)) per session.
    new_score = (
        _combine_session_scores(normalized_a)
        + _combine_session_scores(normalized_b)
        + _combine_session_scores(normalized_c)
    )

    # A single-value session normalizes to 1.0 (see _min_max_normalize
    # docstring: "1.0 if only one row") -- so under the OLD formula, the
    # 6-row session_a contributes sum(normalized_a) = 6.0 * (its own
    # min-max-normalized scale, here exactly 1.0+0.8+0.6+0.4+0.2+0.0 = 3.0),
    # already exceeding b+c's combined 2.0 -- one busy session, mostly
    # MODERATE matches, outweighs two sessions with one STRONG match each.
    assert old_score > (1.0 + 1.0), (
        f"fixture did not reproduce the original bug: expected the busy "
        f"session_a to push old_score past 2.0 (b+c alone), got {old_score}"
    )

    # Under the NEW formula, session_a's contribution is capped at the mean
    # of its own top-SESSION_SCORE_TOP_K values (<=1.0), so it can no longer
    # outweigh b+c (which each contribute exactly 1.0, their single value).
    assert new_score <= old_score, (
        f"new formula ({new_score}) should never exceed the old formula's "
        f"sum-of-sums ({old_score}) on this fixture"
    )
    assert new_score == pytest.approx(
        _combine_session_scores(normalized_a) + 1.0 + 1.0
    )
    # The key proof: session_a's OWN contribution is now <= 1.0 (capped),
    # not 3.0 (its old, uncapped sum).
    assert _combine_session_scores(normalized_a) <= 1.0
    assert sum(normalized_a) == pytest.approx(3.0)


def test_combine_session_scores_drops_subthreshold_values():
    # All values at/below MIN_RELEVANCE_THRESHOLD (0.2) must not count.
    assert _combine_session_scores([0.2, 0.1, 0.0]) == 0.0


def test_combine_session_scores_empty_input():
    assert _combine_session_scores([]) == 0.0


# ---------------------------------------------------------------------------
# 3. Minimum evidence count gate -- real Postgres, real pipeline.
# ---------------------------------------------------------------------------
def test_min_evidence_gate_blocks_candidate_row_with_thin_evidence(
    session_repo_root, pg_config
):
    """A single session, per_session_limit=1 -> at most 1 provenance ref
    total, which is below MIN_PROVENANCE_REFS_FOR_CANDIDATE (2) -- no
    shared_core.candidates row must be written at all.
    """
    keyword = f"thin-evidence-keyword-{uuid.uuid4().hex[:8]}"
    session_id = _seed_session(
        pg_config,
        turns=[
            f"A note mentioning {keyword} exactly once in this whole session.",
            "An unrelated filler turn about synthetic fixture-corp logistics.",
        ],
    )

    result = aggregate_cross_session(
        keyword,
        [session_id],
        session_repo_root=session_repo_root,
        per_session_limit=1,
    )

    assert len(result.provenance_refs) < MIN_PROVENANCE_REFS_FOR_CANDIDATE
    assert result.candidate_id is None, (
        "expected no shared_core.candidates row when provenance_refs is "
        f"below the minimum evidence gate, got candidate_id={result.candidate_id!r}"
    )
    assert result.fingerprint is None

    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM shared_core.candidates WHERE keyword_description = %s",
                (keyword,),
            )
            assert cur.fetchone()[0] == 0, (
                "a shared_core.candidates row exists despite the thin-evidence gate"
            )


# ---------------------------------------------------------------------------
# 4. Idempotent upsert + provenance_refs merge -- real Postgres, real
#    pipeline, run TWICE.
# ---------------------------------------------------------------------------
def test_rerun_same_aggregation_upserts_not_duplicates(session_repo_root, pg_config):
    phrase = f"idempotency-rerun-phrase-{uuid.uuid4().hex[:8]}"
    session_a = _seed_session(
        pg_config,
        turns=[
            f"First mention of {phrase} in this synthetic fixture session.",
            "Unrelated filler about synthetic fixture-corp scheduling.",
        ],
    )
    session_b = _seed_session(
        pg_config,
        turns=[
            f"Second session also discusses {phrase} for the fixture pipeline.",
            "Another unrelated filler turn about fixture-corp snacks.",
        ],
    )
    session_ids = [session_a, session_b]

    # --- before: confirm zero rows for this brand-new keyword -----------
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM shared_core.candidates WHERE keyword_description = %s",
                (phrase,),
            )
            count_before_any_run = cur.fetchone()[0]
    assert count_before_any_run == 0

    result_1 = aggregate_cross_session(
        phrase, session_ids, session_repo_root=session_repo_root
    )
    assert result_1.candidate_id is not None
    assert result_1.fingerprint is not None

    count_after_run_1 = _candidate_count_for_fingerprint(pg_config, result_1.fingerprint)
    assert count_after_run_1 == 1

    # --- rerun: SAME keyword_description, SAME session_id set -----------
    result_2 = aggregate_cross_session(
        phrase, session_ids, session_repo_root=session_repo_root
    )

    assert result_2.fingerprint == result_1.fingerprint, (
        "same (keyword_description, session_id set) must produce the SAME fingerprint"
    )
    assert result_2.candidate_id == result_1.candidate_id, (
        f"rerun produced a DIFFERENT candidate_id ({result_2.candidate_id}) than the "
        f"first run ({result_1.candidate_id}) -- upsert did not target the same row"
    )

    count_after_run_2 = _candidate_count_for_fingerprint(pg_config, result_1.fingerprint)
    assert count_after_run_2 == 1, (
        f"expected exactly 1 row after 2 runs of the same aggregation (idempotent "
        f"upsert), got {count_after_run_2} -- a duplicate row was inserted"
    )

    # --- provenance_refs merged, not lost or duplicated ------------------
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT provenance_refs FROM shared_core.candidates WHERE candidate_id = %s",
                (result_1.candidate_id,),
            )
            (final_refs,) = cur.fetchone()

    # The two runs queried the exact same sessions with the exact same
    # query, so they returned the SAME underlying chunks both times --
    # the merge must DEDUPLICATE, not append duplicates, so the final
    # ref count must equal a single run's ref count, not double it.
    assert len(final_refs) == len(result_1.provenance_refs), (
        f"expected the merged provenance_refs ({len(final_refs)}) to equal a single "
        f"run's count ({len(result_1.provenance_refs)}) since both runs returned "
        f"identical underlying chunks -- merge must dedupe, not duplicate"
    )
    assert len(final_refs) > 0, "provenance_refs must not have been lost by the upsert"
    refs_session_ids = {ref["session_id"] for ref in final_refs}
    assert refs_session_ids == set(session_ids), (
        "provenance_refs after the upsert must still cover both source sessions"
    )
