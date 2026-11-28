"""Claude and Codex engineers
=============================

Each engineer uses its own subscription and credentials.
Start with claude-1, codex-1, add claude-2, codex-2 when needed.
"""

from os import getenv
from pathlib import Path
from typing import Any

from agno.agents.claude import ClaudeAgent
from agno.agents.codex import CodexAgent

from app.sandbox import REPOSITORY, sandbox_provider
from db import get_postgres_db

db = get_postgres_db()
sandbox = sandbox_provider()
if sandbox is not None and REPOSITORY is None:
    raise ValueError("Set REPOSITORY in app/sandbox.py before enabling a sandbox.")
repository = None if sandbox is None else REPOSITORY
cwd = str(Path(__file__).resolve().parents[1]) if sandbox is None else None


def credential(parameter: str, setting: str) -> dict[str, Any]:
    """The engineer's subscription credentials.

    A setting that is present but empty is passed on, so the run fails and says so
    instead of quietly using the API key.
    """
    value = getenv(setting)
    return {} if value is None else {parameter: value}


def create_claude_engineer(number: int = 1) -> ClaudeAgent:
    return ClaudeAgent(
        id=f"claude-{number}",
        name=f"Claude {number}",
        model="claude-opus-5-5",
        db=db,
        cwd=cwd,
        sandbox=sandbox,
        repository=repository,
        system_prompt={"type": "preset", "preset": "claude_code"},
        permission_mode="auto",
        **credential("oauth_token", f"CLAUDE_{number}_OAUTH_TOKEN"),
    )


def create_codex_engineer(number: int = 1) -> CodexAgent:
    # On a ChatGPT sign-in (auth.json) this engineer can only run one at a time.
    # Use an access token for concurrent sessions.
    return CodexAgent(
        id=f"codex-{number}",
        name=f"Codex {number}",
        model="gpt-6.1-sol",
        db=db,
        cwd=cwd,
        sandbox=sandbox,
        repository=repository,
        # Codex wraps each command in a sandbox of its own, which cannot start inside a sandbox
        # container. A sandboxed engineer is confined by its sandbox; on the API host Codex's own
        # sandbox is the only protection, so it stays.
        sandbox_mode="workspace-write" if sandbox is None else "full-access",
        approval_mode="auto_review",
        **credential("auth_json", f"CODEX_{number}_AUTH_JSON"),
        **credential("access_token", f"CODEX_{number}_ACCESS_TOKEN"),
    )
