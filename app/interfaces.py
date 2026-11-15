"""Authorize AgentOS and reach Super Agent through MCP and, when configured, Slack."""

from os import getenv

from agno.os import AgentOS, AgentOSBuiltinAuth, Authorization, MCPConfig

# os.agno.com's member role, without its own org, os and billing scopes: what a Slack sender may do
SLACK_MEMBER_SCOPES = [
    "config:read",
    "config:write",
    "registry:read",
    "agents:read",
    "agents:write",
    "agents:run",
    "teams:read",
    "teams:write",
    "teams:run",
    "workflows:read",
    "workflows:write",
    "workflows:run",
    "sessions:read",
    "sessions:write",
    "memories:read",
    "memories:write",
    "knowledge:read",
    "knowledge:write",
    "learnings:read",
    "learnings:write",
    "metrics:read",
    "metrics:write",
    "evals:read",
    "evals:write",
    "traces:read",
    "schedules:read",
    "schedules:write",
    "approvals:read",
    "approvals:write",
    "components:read",
    "components:write",
    "filesystem:read",
    "products:read",
    "products:write",
    "projects:read",
    "projects:write",
    "tasks:read",
    "tasks:write",
    "sources:read",
    "sources:write",
    "routines:read",
    "routines:write",
    "wiki:read",
    "wiki:write",
    "decisions:read",
    "decisions:write",
]


def mcp_auth(agentos_url: str) -> AgentOSBuiltinAuth | None:
    """Enable MCP OAuth when the MCP_CONNECT_SECRET is provided."""
    secret = getenv("MCP_CONNECT_SECRET")
    if not secret:
        return None
    return AgentOSBuiltinAuth(url=agentos_url, secret=secret)


def authorization(runtime_env: str) -> Authorization | None:
    """Enable os.agno.com authorization outside dev, with a default role for Slack senders."""
    if runtime_env == "dev":
        return None
    authz = Authorization(trust_token_scopes=True, roles_claim="role")
    authz.define_role("member", SLACK_MEMBER_SCOPES, default=True)
    return authz


def attach_interfaces(agent_os: AgentOS) -> None:
    """Publish Super Agent alongside the built-in MCP tools; optionally attach Slack."""
    manager = agent_os.manager
    if manager is None:
        raise RuntimeError("Super Agent must be configured before attaching interfaces.")
    agent_os.mcp = MCPConfig(
        tools=[
            manager.as_tool(
                name="super_agent",
                title="Super Agent",
                description="Talk to Super Agent on this AgentOS.",
            )
        ],
        default_tools=True,
    )
    token, secret = getenv("SLACK_BOT_TOKEN"), getenv("SLACK_SIGNING_SECRET")
    if token and secret:
        from agno.os.interfaces.slack import Slack

        agent_os.interfaces.append(
            Slack(
                team=manager,
                token=token,
                streaming=True,
                signing_secret=secret,
                resolve_user_identity=True,
                loading_text="Pulling the thread...",
            )
        )
