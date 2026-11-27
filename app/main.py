"""
AgentOS Entrypoint
==================
"""

from os import getenv
from pathlib import Path
from typing import Any

from agno.job_queue import QueueConfig
from agno.os import AgentOS, CompanyConfig, OSManager
from agno.os.authz import PLATFORM, READ, RUN, Authorization, Role, UserDirectory

from agents.engineers import create_claude_engineer, create_codex_engineer
from app.company import goals
from app.interfaces import attach_interfaces, mcp_auth
from app.registry import registry, shared_knowledge, shared_learning
from app.settings import super_agent_model
from db import get_postgres_db
from workflows.merge_ready import merge_ready_workflows

runtime_env = getenv("RUNTIME_ENV", "prd")
agentos_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")
agentos_root = Path(__file__).resolve().parent.parent
db = get_postgres_db()

# A new user is a member: they read and run your agents, teams and workflows.
# Move a user to platform in user management to give them Super Agent.
member = Role("member", scopes=[*READ, *RUN])
platform = Role("platform", scopes=[*READ, *RUN, *PLATFORM])

agents: list[Any] = [
    create_claude_engineer(),
    create_codex_engineer(),
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
        # A working conversation runs long; five turns of history loses its start.
        num_history_runs=20,
    ),
    company=CompanyConfig(
        goals=goals,
        model=super_agent_model(),
    ),
    queue=QueueConfig(durable=True, db=db),
    knowledge=[shared_knowledge],
    agents=agents,
    # "PR to merge-ready": registered when both engineers above are enabled and run in sandboxes.
    workflows=merge_ready_workflows(agents) or None,
    registry=registry,
    config=str(agentos_root / "app" / "config.yaml"),
)
attach_interfaces(agent_os)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="app.main:app", host="127.0.0.1", port=8000, reload=False)
