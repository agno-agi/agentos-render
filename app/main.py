"""
AgentOS Entrypoint
==================
"""

from os import getenv
from pathlib import Path
from typing import Any

from agno.compaction import Compaction
from agno.job_queue import QueueConfig
from agno.os import AgentOS, CompanyConfig, OSManager
from agno.os.authz import PLATFORM, READ, RUN, Authorization, Role, UserDirectory

# from agents.engineers import create_claude_engineer
# from agents.engineers import create_codex_engineer
from app.company import goals
from app.github import github_instructions, github_read_tools
from app.interfaces import attach_interfaces, mcp_auth
from app.registry import registry, shared_knowledge, shared_learning
from app.settings import super_agent_model
from db import get_postgres_db

runtime_env = getenv("RUNTIME_ENV", "prd")
agentos_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")
agentos_root = Path(__file__).resolve().parent.parent
db = get_postgres_db()

# Every user starts as a member with read and run permissions.
# Give a user the platform role (in user management) to give them Super Agent.
member = Role("member", scopes=[*READ, *RUN])
platform = Role("platform", scopes=[*READ, *RUN, *PLATFORM])

agents: list[Any] = [
    # create_claude_engineer(),
    # create_codex_engineer(),
]

agent_os = AgentOS(
    db=db,
    mcp=True,
    tracing=True,
    scheduler=True,
    user_isolation=True,
    user_directory=UserDirectory(default_role=member),
    scheduler_base_url=agentos_url,
    mcp_auth=mcp_auth(agentos_url),
    authorization=Authorization(roles=[member, platform]) if runtime_env != "dev" else False,
    manager=OSManager(
        root=agentos_root,
        model=super_agent_model(),
        learning=shared_learning,
        # A long conversation is summarized once it passes 100,000 tokens.
        # A request the model refuses as too long is summarized and sent again.
        compaction=Compaction(compact_at_tokens=100_000, on_context_overflow=True),
        # Read-only GitHub functions, when GITHUB_READ_TOKEN or GH_TOKEN is set.
        tools=github_read_tools(),
        instructions=github_instructions(),
    ),
    company=CompanyConfig(
        goals=goals,
        model=super_agent_model(),
    ),
    queue=QueueConfig(durable=True, db=db),
    knowledge=[shared_knowledge],
    agents=agents,
    registry=registry,
    config=str(agentos_root / "app" / "config.yaml"),
)
attach_interfaces(agent_os)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="app.main:app", host="127.0.0.1", port=8000, reload=False)
