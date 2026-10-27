"""Opt-in Claude and Codex engineers. Register factory results in app/main.py."""

from os import getenv
from pathlib import Path

from agno.agents.claude import ClaudeAgent
from agno.agents.codex import CodexAgent
from agno.sandbox import Repository, Sandbox

from app.sandbox import REPOSITORY, sandbox_provider
from db import get_postgres_db


def _execution_config() -> tuple[Sandbox | None, Repository | None, str | None]:
    sandbox = sandbox_provider()
    if sandbox is None:
        return None, None, str(Path(__file__).resolve().parents[1])
    if REPOSITORY is None:
        raise ValueError("Set REPOSITORY in app/sandbox.py before enabling a sandbox.")
    return sandbox, REPOSITORY, None


def create_claude_engineer() -> ClaudeAgent:
    """Enable Claude explicitly with credentials; sandboxing is optional."""
    sandbox, repository, cwd = _execution_config()
    uses_bedrock = sandbox is not None and (sandbox.env or {}).get("CLAUDE_CODE_USE_BEDROCK") == "1"
    if not (getenv("ANTHROPIC_API_KEY") or getenv("CLAUDE_CODE_OAUTH_TOKEN") or uses_bedrock):
        raise ValueError(
            "Set ANTHROPIC_API_KEY before enabling Claude Engineer; see docs/sandboxes.md for alternatives."
        )
    return ClaudeAgent(
        id="claude-engineer",
        name="Claude Engineer",
        model="claude-opus-5-5",
        db=get_postgres_db(),
        cwd=cwd,
        sandbox=sandbox,
        repository=repository,
        system_prompt={"type": "preset", "preset": "claude_code"},
        permission_mode="acceptEdits",
    )


def create_codex_engineer() -> CodexAgent:
    """Enable Codex explicitly with credentials; sandboxing is optional."""
    sandbox, repository, cwd = _execution_config()
    if not getenv("OPENAI_API_KEY"):
        raise ValueError("Set OPENAI_API_KEY before enabling Codex Engineer.")
    return CodexAgent(
        id="codex-engineer",
        name="Codex Engineer",
        model="gpt-6.1-sol",
        db=get_postgres_db(),
        cwd=cwd,
        sandbox=sandbox,
        repository=repository,
        sandbox_mode="workspace-write",
    )
