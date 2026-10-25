"""Application smoke checks. Run with python -m evals."""

from agno.eval import Case

from app.main import agent_os

CASES = (
    Case(
        name="manager_explains_engineer_recovery",
        team=agent_os.manager,
        input="Read README.md and docs/sandboxes.md. I want to deploy this template on Render and use Claude and "
        "Codex engineers. What survives an API replacement, how do I get isolated engineering with durable recovery, "
        "and do I need an attached disk? Do not configure or change anything.",
        criteria="Explain that PostgreSQL preserves saved conversations and Company records, but does not recreate "
        "the engineer workspace or native session. Direct engineer files/native state may be lost on replacement. "
        "Describe optional AgentCore with S3 checkpoints, no attached API disk, and recovery from the last saved "
        "checkpoint rather than exact crash-time state. Do not claim this deployment has been provisioned or tested.",
        expected_tool_calls=("read_file",),
        user_id="render-recovery-regression",
        tags=("deployment",),
    ),
    Case(
        name="manager_explains_simple_local_start",
        team=agent_os.manager,
        input="Read README.md and example.env. I only want to try this platform locally using Docker Compose. "
        "Give the exact startup command and credential variable names for both included engineers. "
        "Which services must I set up first? Explain where the engineers edit files and whether I need "
        "AWS, Redis or a GitHub repository just to start. Do not start services or change any files.",
        criteria="Give the documented Compose startup and OpenAI key requirement. Explain that Claude needs its "
        "own API key or OAuth credential when used. AWS, Redis, a sandbox and a remote GitHub repository are not "
        "required for basic local startup. Both engineers are available and direct execution can edit the mounted "
        "project checkout, including running code. Do not describe Compose alone as isolated engineering.",
        expected_tool_calls=("read_file",),
        user_id="render-local-regression",
        tags=("deployment",),
    ),
    Case(
        name="manager_explains_application",
        team=agent_os.manager,
        input="Read README.md. Explain how to start this application, talk to OS Manager and add an agent. "
        "Do not create or change anything.",
        criteria="Give actionable startup instructions grounded in README.md, including .env and OPENAI_API_KEY "
        "configuration, the startup command, a documented way to chat with OS Manager, and how to add an agent. "
        "Do not claim to have started the application or created an agent.",
        expected_tool_calls=("read_file",),
        tags=("smoke",),
    ),
    Case(
        name="manager_checks_health",
        team=agent_os.manager,
        input="Run diagnostics and report this AgentOS's health. Do not change any state or run other components.",
        criteria="Report the observed diagnostics accurately, including any problems. Do not present a "
        "configuration/database check as proof that agents executed or that production is healthy.",
        expected_tool_calls=("run_diagnostics",),
        tags=("smoke",),
    ),
    Case(
        name="manager_explains_configured_learning",
        team=agent_os.manager,
        input="Read app/registry.py. What learning is configured in this app, and does it retrain the model? "
        "Do not change anything.",
        criteria="Explain that app/registry.py configures shared_learning as a LearningMachine backed by "
        "PostgreSQL, with user profiles and user memories in AGENTIC mode. It persists information outside "
        "model weights and does not retrain the model. Ground claims in the file; do not invent additional "
        "enabled stores or claim a successful live learning test.",
        expected_tool_calls=("read_file",),
        tags=("smoke",),
    ),
)
