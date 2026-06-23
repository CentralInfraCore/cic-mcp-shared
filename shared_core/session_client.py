"""Real subprocess + stdio MCP client for the cic-mcp-session MCP server.

Job: shared-cross-session-aggregator-implementation-001, "Feladat" 2 ("MCP
subprocess-launch — grep + minta-követés").

Source of truth for the launch pattern this module REUSES (not reinvented):
cic-mcp-gateway/gateway_core/compile_context.py:70
(`class SessionServerLaunchConfig`) and :97 (`StdioServerParameters(...)`
inside `SessionServerLaunchConfig.to_stdio_params()`). That dataclass starts
cic-mcp-session's `mcp-server/session_server.py` as a REAL, independent
subprocess via `.venv-host/bin/python`, talked to over real
`mcp.client.stdio` (NOT an in-process import of session_server.py's tool
functions, and NOT a mock) -- this module mirrors that exact shape, only
swapping which tool(s) get called once the session is connected
(`search_session_context` here, vs. `get_session_status` +
`get_session_context_pack` in compile_context.py).

`SessionServerLaunchConfig` below is intentionally near-identical to
gateway_core/compile_context.py:70-99 -- the cic-mcp-shared repo does not
import cic-mcp-gateway as a dependency (no cross-repo Python import,
per cic-mcp-shared/CLAUDE.md "Fő határok": shared does not reach into
gateway's package), so the dataclass is reproduced here rather than
imported, with the launch SHAPE kept identical, not "inspired by".
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# The cic-mcp-session subprocess reads its DB connection params from these
# env vars (session_store/envelope_writer.py:SessionStoreConfig.from_env()).
# StdioServerParameters.env, when set, REPLACES the subprocess environment
# entirely (mcp.client.stdio.get_default_environment() is only used when
# env=None) -- so these must be explicitly forwarded, or the subprocess
# silently falls back to from_env()'s own defaults (localhost:5432/postgres)
# instead of the actual test/dev Postgres instance this process is using.
# Identical list to gateway_core/compile_context.py:46-52.
_SESSION_STORE_ENV_VARS = (
    "SESSION_STORE_PG_HOST",
    "SESSION_STORE_PG_PORT",
    "SESSION_STORE_PG_DB",
    "SESSION_STORE_PG_USER",
    "SESSION_STORE_PG_PASSWORD",
)


@dataclass(frozen=True)
class SessionServerLaunchConfig:
    """Where/how to start the cic-mcp-session MCP server as a subprocess.

    Mirrors cic-mcp-session/.mcp.json.tpl's "cic-session" entry exactly, via
    the same shape as gateway_core/compile_context.py:70-99
    (`SessionServerLaunchConfig`) -- this dataclass does NOT invent a new
    launch convention.
    """

    repo_root: Path
    python_executable: Path | None = None

    def to_stdio_params(self) -> StdioServerParameters:
        # IMPORTANT: do NOT call Path.resolve()/realpath() on python_exe --
        # .venv-host/bin/python is a symlink to the system interpreter
        # (standard venv layout); resolving it collapses the path to the
        # bare system python3, which lacks the venv's installed packages
        # (psycopg, mcp, ...) and makes the subprocess fail at import time.
        # Only the REPO ROOT is normalized to an absolute path (harmless,
        # not a symlink-follow-through-a-venv case). Same rationale as
        # gateway_core/compile_context.py:84-90.
        repo_root_abs = self.repo_root.absolute()
        python_exe = self.python_executable or (repo_root_abs / ".venv-host" / "bin" / "python")
        server_script = repo_root_abs / "mcp-server" / "session_server.py"
        env = {"PYTHONPATH": str(repo_root_abs)}
        for var in _SESSION_STORE_ENV_VARS:
            value = os.environ.get(var)
            if value is not None:
                env[var] = value
        return StdioServerParameters(
            command=str(python_exe),
            args=[str(server_script)],
            env=env,
        )


def _decode_tool_result(call_tool_result: Any) -> Any:
    """Decode a CallToolResult into its underlying Python value.

    Same approach as gateway_core/compile_context.py's `_decode_tool_result`
    (mirrored here, not imported, for the same cross-repo-import reason as
    SessionServerLaunchConfig above) -- per that module's docstring,
    EMPIRICALLY verified against the actual running cic-mcp-session server
    (mcp SDK 1.28.0): FastMCP's stdio transport for THIS server does not
    populate .structuredContent for these tools, it serializes the tool's
    Python return value (list[dict] or dict) as a single JSON TextContent
    block in .content[0].text. .structuredContent is still checked first in
    case a future SDK/server version populates it (forward-compatible, not
    required by current evidence).
    """
    import json

    structured = getattr(call_tool_result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    content = getattr(call_tool_result, "content", None) or []
    if content and getattr(content[0], "text", None) is not None:
        return json.loads(content[0].text)
    return None


@asynccontextmanager
async def session_mcp_client(launch_config: SessionServerLaunchConfig):
    """Async context manager yielding a connected, initialized ClientSession
    talking to a REAL cic-mcp-session MCP server subprocess.

    Usage:
        async with session_mcp_client(launch_config) as session:
            result = await session.call_tool("search_session_context", {...})
    """
    server_params = launch_config.to_stdio_params()
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def search_session_context(
    session: ClientSession, session_id: str, query: str, limit: int = 20
) -> list[dict]:
    """Call the REAL `search_session_context(session_id, query, limit)` MCP
    tool (cic-mcp-session/mcp-server/session_server.py:94-95) over an
    already-connected ClientSession, and decode the result into a
    list[dict] with keys chunk_id, turn_id, text, fused_score (the exact
    return shape documented at session_server.py:121-124, NOT
    reimplemented/recomputed here).
    """
    result = await session.call_tool(
        "search_session_context",
        {"session_id": session_id, "query": query, "limit": limit},
    )
    decoded = _decode_tool_result(result)
    return decoded if isinstance(decoded, list) else []
