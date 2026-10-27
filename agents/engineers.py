"""Opt-in Claude and Codex engineers. Register factory results in app/main.py."""

from os import getenv

from agno.agents.claude import ClaudeAgent
from agno.agents.codex import CodexAgent
from agno.sandbox import Repository, Sandbox

from app.sandbox import REPOSITORY, sandbox_provider
from db import get_postgres_db


def _configured_sandbox() -> tuple[Sandbox, Repository]:
    sandbox = sandbox_provider()
    if sandbox is None:
        raise ValueError("Configure a sandbox in app/sandbox.py before enabling an engineer; see docs/sandboxes.md.")
    if REPOSITORY is None:
        raise ValueError("Set REPOSITORY in app/sandbox.py before enabling an engineer.")
    return sandbox, REPOSITORY


def create_claude_engineer() -> ClaudeAgent:
    """Enable Claude explicitly after configuring its sandbox and credentials."""
    sandbox, repository = _configured_sandbox()
    uses_bedrock = (sandbox.env or {}).get("CLAUDE_CODE_USE_BEDROCK") == "1"
    if not (getenv("ANTHROPIC_API_KEY") or getenv("CLAUDE_CODE_OAUTH_TOKEN") or uses_bedrock):
        raise ValueError(
            "Set ANTHROPIC_API_KEY before enabling Claude Engineer; see docs/sandboxes.md for alternatives."
        )
    return ClaudeAgent(
        id="claude-engineer",
        name="Claude Engineer",
        model="claude-opus-5-5",
        db=get_postgres_db(),
        sandbox=sandbox,
        repository=repository,
        system_prompt={"type": "preset", "preset": "claude_code"},
        permission_mode="acceptEdits",
    )


def create_codex_engineer() -> CodexAgent:
    """Enable Codex explicitly after configuring its sandbox and credentials."""
    sandbox, repository = _configured_sandbox()
    if not getenv("OPENAI_API_KEY"):
        raise ValueError("Set OPENAI_API_KEY before enabling Codex Engineer.")
    return CodexAgent(
        id="codex-engineer",
        name="Codex Engineer",
        model="gpt-6.1-sol",
        db=get_postgres_db(),
        sandbox=sandbox,
        repository=repository,
        sandbox_mode="workspace-write",
    )
