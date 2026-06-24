"""Regression tests for the SOURCE_DIR write-confinement fix.

Background: update_companion() and record_decision() in mcp-server/server.py
historically accepted a client-supplied file_path/companion_path as an
absolute path with NO containment check before opening it for writing
(p.open("w")). This let any MCP client overwrite arbitrary host files
reachable by the server process — not just companion YAMLs inside
SOURCE_DIR.

The fix adds _resolve_within_source_dir(), which resolves the candidate path
and SOURCE_DIR with Path.resolve() and checks containment with
Path.is_relative_to() (NOT a string-prefix comparison, which is bypassable
via symlinks or '..' segments).

These tests prove, with real pytest runs against the actual functions
(no mocking of the path-resolution logic itself):
  1. update_companion() rejects an out-of-SOURCE_DIR absolute path AND
     leaves the target file untouched (no write attempt succeeds).
  2. update_companion() still works for a legitimate SOURCE_DIR-relative
     companion YAML (no regression).
  3. record_decision() rejects an out-of-SOURCE_DIR companion_path AND
     leaves the target file untouched.
  4. record_decision() still works for a legitimate SOURCE_DIR-relative
     companion_path (no regression).
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../mcp-server")))

import server as mcp_server  # noqa: E402


@pytest.fixture
def isolated_source_dir(tmp_path, monkeypatch):
    """Point SOURCE_DIR at a throwaway tmp_path directory for the duration of
    the test, and clear the load_kb() LRU cache so tests don't leak state."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    monkeypatch.setattr(mcp_server, "SOURCE_DIR", source_dir)
    mcp_server.load_kb.cache_clear()
    yield source_dir


@pytest.fixture
def outside_file(tmp_path):
    """A pre-existing file OUTSIDE SOURCE_DIR (sibling dir, not a descendant)."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    victim = outside_dir / "victim.yaml"
    victim.write_text('description: "legit pre-existing file, NOT part of SOURCE_DIR"\n')
    return victim


@pytest.fixture
def legit_companion(isolated_source_dir):
    """A pre-existing companion YAML INSIDE SOURCE_DIR."""
    companion = isolated_source_dir / "pkg" / "companion.yaml"
    companion.parent.mkdir(parents=True)
    companion.write_text("description: \"\"\ncategory: []\n")
    return companion


# ---------------------------------------------------------------------------
# _resolve_within_source_dir() — unit-level containment checks
# ---------------------------------------------------------------------------

class TestResolveWithinSourceDir:
    def test_rejects_absolute_path_outside_source_dir(self, isolated_source_dir, outside_file):
        with pytest.raises(ValueError):
            mcp_server._resolve_within_source_dir(str(outside_file))

    def test_rejects_dotdot_traversal(self, isolated_source_dir):
        with pytest.raises(ValueError):
            mcp_server._resolve_within_source_dir("../escape.yaml")

    def test_accepts_relative_path_inside_source_dir(self, legit_companion, isolated_source_dir):
        resolved = mcp_server._resolve_within_source_dir("pkg/companion.yaml")
        assert resolved == legit_companion.resolve()

    def test_accepts_absolute_path_inside_source_dir(self, legit_companion, isolated_source_dir):
        resolved = mcp_server._resolve_within_source_dir(str(legit_companion))
        assert resolved == legit_companion.resolve()


# ---------------------------------------------------------------------------
# update_companion() — rejection AND no-regression
# ---------------------------------------------------------------------------

class TestUpdateCompanionConfinement:
    def test_rejects_out_of_source_dir_absolute_path(self, isolated_source_dir, outside_file):
        before = outside_file.read_text()

        result = mcp_server.update_companion(
            file_path=str(outside_file),
            description="PWNED by path traversal",
        )

        assert result["success"] is False
        assert "escapes SOURCE_DIR" in result["message"]
        # The target file must NOT have been modified — the write must never
        # have been attempted.
        assert outside_file.read_text() == before
        assert "PWNED" not in outside_file.read_text()

    def test_legit_companion_update_still_works(self, legit_companion, isolated_source_dir):
        result = mcp_server.update_companion(
            file_path="pkg/companion.yaml",
            description="legit update works",
            category=["foo"],
        )

        assert result["success"] is True
        assert "description" in result["updated_fields"]
        content = legit_companion.read_text()
        assert "legit update works" in content
        assert "foo" in content


# ---------------------------------------------------------------------------
# record_decision() — rejection AND no-regression
# ---------------------------------------------------------------------------

class TestRecordDecisionConfinement:
    def test_rejects_out_of_source_dir_companion_path(self, isolated_source_dir, outside_file):
        before = outside_file.read_text()
        fake_kb = {"nodes": {}}

        with patch.object(mcp_server, "load_kb", return_value=fake_kb):
            result = mcp_server.record_decision(
                node_id="n1",
                decision="PWNED by path traversal",
                companion_path=str(outside_file),
            )

        assert result["success"] is False
        assert "escapes SOURCE_DIR" in result["message"]
        assert outside_file.read_text() == before
        assert "PWNED" not in outside_file.read_text()

    def test_legit_decision_record_still_works(self, legit_companion, isolated_source_dir):
        fake_kb = {"nodes": {}}

        with patch.object(mcp_server, "load_kb", return_value=fake_kb):
            result = mcp_server.record_decision(
                node_id="n1",
                decision="legit decision works",
                rationale="no regression",
                companion_path="pkg/companion.yaml",
            )

        assert result["success"] is True
        content = legit_companion.read_text()
        assert "legit decision works" in content
        assert "no regression" in content
