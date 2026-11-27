"""Claude and Codex engineers for coding tasks.

Each engineer is a worker with a sign-in of its own: claude-1, codex-1, and later claude-2,
codex-2. Give one a plan credential and it runs on that plan and is never given the API key:

    CLAUDE_<n>_PLAN_TOKEN   a token from `claude setup-token`
    CODEX_<n>_PLAN_LOGIN    the contents of the auth.json that `codex login` writes

Without one, the engineer uses ANTHROPIC_API_KEY or OPENAI_API_KEY. See README.md.
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


def plan_credential(parameter: str, setting: str) -> dict[str, Any]:
    """The engineer's plan credential as a constructor argument; nothing when the setting is not set.

    A setting that is present but empty is passed on, so the engineer's run fails and says so
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
        **plan_credential("plan_token", f"CLAUDE_{number}_PLAN_TOKEN"),
    )


def create_codex_engineer(number: int = 1) -> CodexAgent:
    # On a plan login this engineer runs one piece of work at a time.
    return CodexAgent(
        id=f"codex-{number}",
        name=f"Codex {number}",
        model="gpt-6.1-sol",
        db=db,
        cwd=cwd,
        sandbox=sandbox,
        repository=repository,
        sandbox_mode="workspace-write",
        approval_mode="auto_review",
        **plan_credential("plan_login", f"CODEX_{number}_PLAN_LOGIN"),
    )
