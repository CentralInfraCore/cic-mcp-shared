"""End-to-end test for shared_core.aggregator.aggregate_cross_session().

Job: shared-cross-session-aggregator-implementation-001, "Feladat" 4
("Valós, futtatott bizonyíték").

This test exercises the FULL real path, same evidence bar as
cic-mcp-gateway/tests/test_gateway_core/test_compile_context.py:
  1. TWO real cic-mcp-session ingest pipeline runs (insert_envelope ->
     run_projection_batch -> run_indexing_batch), against a REAL Postgres
     instance -- same chain as cic-mcp-session/tests/test_session_store/
     test_session_api.py (_run_chain_for_envelope). NOT mocked, NOT a
     hand-written SQL INSERT into session_core/session_idx.
  2. aggregate_cross_session(), which starts the cic-mcp-session MCP server
     as a REAL, independent subprocess (shared_core.session_client.
     SessionServerLaunchConfig, mirroring gateway_core/compile_context.py:70)
     and talks to it via real mcp.client.stdio (NOT an in-process call, NOT
     a mock).
  3. a real psql-equivalent (psycopg) SELECT against shared_core.candidates
     after the run, proving the INSERTed row's actual weight_score/
     recurrence_count/provenance_refs values.

ALL session fixture content below is SYNTHETIC/FABRICATED (per input.md
"Forbidden Shortcuts": "valós, személyes session-tartalom használata a
teszt-fixture-ökben" is forbidden, same rule as historical-dedupe-
idempotency-001) -- two distinct sessions, each containing the shared
keyword phrase "factory job lifecycle audit" so the cross-session aggregator
has a genuine multi-session recurring signal to detect, plus filler turns
that do NOT contain the phrase (to keep min-max normalization meaningful
within each session).

Requires:
  - a reachable Postgres instance with ALL cic-mcp-session schema/migration
    files AND the shared_core.candidates schema (shared-core-storage-
    implementation-001/output/shared-core-storage-schema.sql) already
    applied, addressed via the SESSION_STORE_PG_* env vars below.
  - SHARED_AGGREGATOR_TEST_SESSION_REPO env var pointing at a
    cic-mcp-session checkout that has .venv-host/bin/python already built
    (`make deps.local` in that checkout) -- this test launches THAT
    checkout's session_server.py as the real MCP subprocess, and also
    imports ITS session_store package (via sys.path) to drive the real
    ingest pipeline, since cic-mcp-session is a read-only dependency for
    this job (input.md Sources: "KIZÁRÓLAG OLVASÁSRA" -- no copy of
    session_store is vendored into cic-mcp-shared).

If SHARED_AGGREGATOR_TEST_SESSION_REPO is unset or Postgres is unreachable,
the test fails loudly (pytest.fail), same "do not silently skip the
real-evidence test" stance as cic-mcp-session's own test_session_api.py.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from shared_core.aggregator import SharedStoreConfig, aggregate_cross_session

SHARED_REPO_ROOT = Path(__file__).resolve().parents[2]

# Synthetic, fabricated phrase shared across both fixture sessions -- the
# recurring "concept" the aggregator is meant to detect. Not real content.
RECURRING_PHRASE = "factory job lifecycle audit checklist"


def _session_repo_root() -> Path:
    raw = os.environ.get("SHARED_AGGREGATOR_TEST_SESSION_REPO")
    if not raw:
        pytest.fail(
            "SHARED_AGGREGATOR_TEST_SESSION_REPO is not set -- point it at a "
            "cic-mcp-session checkout with .venv-host/bin/python already built "
            "(make deps.local) and ALL schema/migration SQL files (including "
            "shared_core.candidates) already applied to the target Postgres "
            "instance."
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
    """Make cic-mcp-session's OWN session_store package importable, so this
    test can call the REAL insert_envelope/run_projection_batch/
    run_indexing_batch functions -- no reimplementation, no copy. Mirrors
    cic-mcp-gateway/tests/test_gateway_core/test_compile_context.py's
    identically-named fixture.
    """
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
        port=int(os.environ.get("SESSION_STORE_PG_PORT", "55435")),
        dbname=os.environ.get("SESSION_STORE_PG_DB", "testdb"),
        user=os.environ.get("SESSION_STORE_PG_USER", "postgres"),
        password=os.environ.get("SESSION_STORE_PG_PASSWORD", "test"),
    )
    try:
        with psycopg.connect(cfg.conninfo(), connect_timeout=5):
            pass
    except psycopg.OperationalError as exc:
        pytest.fail(
            "Cannot reach a real Postgres instance for the aggregate_cross_session() "
            f"end-to-end test. Original error: {exc}"
        )
    # Propagate to the env so the aggregator's MCP subprocess (which reads
    # SessionStoreConfig.from_env() inside session_server.py) AND the
    # SharedStoreConfig.from_env() used for the shared_core.candidates
    # INSERT both target the SAME instance as this test's own direct
    # pipeline calls.
    os.environ["SESSION_STORE_PG_HOST"] = cfg.host
    os.environ["SESSION_STORE_PG_PORT"] = str(cfg.port)
    os.environ["SESSION_STORE_PG_DB"] = cfg.dbname
    os.environ["SESSION_STORE_PG_USER"] = cfg.user
    os.environ["SESSION_STORE_PG_PASSWORD"] = cfg.password
    return cfg


def _valid_envelope(**overrides) -> dict:
    """Mirrors cic-mcp-session/tests/test_session_store/test_session_api.py
    :_valid_envelope exactly (field-for-field) -- not reinvented.
    """
    base = {
        "apiVersion": "cic.session/v1",
        "kind": "SessionIngressEnvelope",
        "event_id": str(uuid.uuid4()),
        "provider": "claude-code",
        "provider_session_id": "shared-aggregator-pytest-session",
        "provider_event_name": "Stop",
        "source": {"kind": "hook", "collector": "log-event.py"},
        "occurred_at": datetime(2026, 6, 23, 13, 0, 0, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 6, 23, 13, 0, 1, tzinfo=timezone.utc),
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
    """Drive ONE fresh session through the REAL ingest chain
    (insert_envelope -> run_projection_batch -> run_indexing_batch) with the
    given list of SYNTHETIC turn texts, and return its session_core.sessions
    session_id. Mirrors cic-mcp-session's own _run_chain_for_envelope /
    cic-mcp-gateway's seeded_session_id fixture pattern.
    """
    from session_store.chunk_indexer import run_indexing_batch
    from session_store.envelope_writer import insert_envelope
    from session_store.turn_projector import run_projection_batch

    provider_session_id = f"shared-aggregator-pytest-{uuid.uuid4().hex[:8]}"
    base_time = datetime(2026, 6, 23, 13, 0, 0, tzinfo=timezone.utc)
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


@pytest.fixture
def two_synthetic_sessions(pg_config) -> list[str]:
    """TWO synthetic, fabricated sessions, each containing the same
    RECURRING_PHRASE among unrelated filler turns -- a genuine multi-session
    recurring-concept fixture, built ENTIRELY through the real ingest chain
    (no hand-crafted session_core/session_idx rows).
    """
    session_a = _seed_session(
        pg_config,
        turns=[
            "Reviewed the quarterly synthetic widget inventory totals for fixture-corp.",
            f"Drafted a {RECURRING_PHRASE} for the fictitious widget-factory pipeline.",
            "Filed a synthetic ticket about the fixture-corp break room coffee machine.",
        ],
    )
    session_b = _seed_session(
        pg_config,
        turns=[
            "Discussed fictitious holiday schedule swaps for the fixture-corp team.",
            f"Updated the {RECURRING_PHRASE} after the fictitious widget-factory retro.",
            "Noted a synthetic reminder to water the office plants at fixture-corp.",
        ],
    )
    return [session_a, session_b]


def test_aggregate_cross_session_real_subprocess_real_postgres(
    session_repo_root, two_synthetic_sessions, pg_config
):
    """Full real path: real DB data (seeded via the real pipeline, two
    sessions) + real MCP subprocess + real shared_core.candidates INSERT,
    verified via a real follow-up SELECT.
    """
    result = aggregate_cross_session(
        RECURRING_PHRASE,
        two_synthetic_sessions,
        session_repo_root=session_repo_root,
        linked_factory_job_ids=["shared-cross-session-aggregator-implementation-001"],
        last_evidence_at=datetime.now(timezone.utc),
    )

    # --- in-process result assertions (actual computed values) ----------
    assert result.recurrence_count >= 2, (
        f"expected recurrence_count >= 2 (both synthetic sessions contain "
        f"the recurring phrase), got {result.recurrence_count}"
    )
    assert result.weight_score > 0.0, f"expected non-trivial weight_score, got {result.weight_score}"
    assert result.factory_linkage_bonus > 0.0, "linked_factory_job_ids was non-empty"
    assert result.recency_bonus > 0.0, "last_evidence_at was just set to now()"
    assert len(result.provenance_refs) >= 2, "expected at least one provenance ref per session"
    assert {ref["session_id"] for ref in result.provenance_refs} == set(two_synthetic_sessions)

    # --- real Postgres follow-up SELECT (proves the row, not just the
    #     in-process return value) --------------------------------------
    with psycopg.connect(pg_config.conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT keyword_description, trust, canonical, weight_score, "
                "recurrence_count, linked_factory_job_ids, recency_flag, "
                "provenance_refs FROM shared_core.candidates WHERE candidate_id = %s",
                (result.candidate_id,),
            )
            row = cur.fetchone()

    assert row is not None, "shared_core.candidates row was not found after INSERT"
    (
        keyword_description,
        trust,
        canonical,
        weight_score,
        recurrence_count,
        linked_factory_job_ids,
        recency_flag,
        provenance_refs,
    ) = row

    assert keyword_description == RECURRING_PHRASE
    assert trust == "candidate"
    assert canonical is False
    assert weight_score == pytest.approx(result.weight_score)
    assert recurrence_count == result.recurrence_count
    assert recurrence_count >= 2
    assert linked_factory_job_ids == ["shared-cross-session-aggregator-implementation-001"]
    assert recency_flag is True
    assert len(provenance_refs) == len(result.provenance_refs)


def test_aggregate_cross_session_no_factory_link_no_recency(
    session_repo_root, two_synthetic_sessions, pg_config
):
    """Negative case for the two additive bonuses: when neither
    linked_factory_job_ids nor a recent last_evidence_at is supplied,
    weight_score must equal cross_session_score exactly (no bonus leakage),
    while recurrence_count is unaffected (it only depends on the
    cross-session search results, not on the bonuses).
    """
    result = aggregate_cross_session(
        RECURRING_PHRASE,
        two_synthetic_sessions,
        session_repo_root=session_repo_root,
    )

    assert result.factory_linkage_bonus == 0.0
    assert result.recency_bonus == 0.0
    assert result.weight_score == pytest.approx(result.cross_session_score)
    assert result.recurrence_count >= 2
