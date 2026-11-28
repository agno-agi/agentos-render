"""
CompanyOS
=========
"""

from pathlib import Path

from agno.company import Goal, Routine, Source

from app.sandbox import REPOSITORY

# Recommended: enable an engineer in app/main.py, then add a line to these instructions
# naming it as the executor for code changes, for example: "Use codex-1 for code changes."
MAINTENANCE = """\
Keep this AgentOS current, secure and working. Propose only demonstrated problems or
released Agno changes affecting this repository. No new features, tables or refactors.
Most runs should propose nothing.

Read AGENTS.md, the Goal status and open Projects and Tasks. Resume unfinished
checks, then scan upgrades, security and quality. Stay within this Goal.
Reserve your last 3 tool calls for updating status.

- Upgrades: compare the current Agno version with newer releases;
  propose relevant upgrades with required checks.
- Security: exposed secrets, weakened authorization, unnecessary tools, dependency advisories.
- Quality: conflicting instructions or configuration, ineffective settings, missing or failing checks.

Resolve code/docs disagreements using Goal context, decisions, tests and history.
Never rewrite docs to excuse weakened protections or tests.
Record unclear decisions in Goal status for a person; do not guess.

When needed, propose one bounded Project per finding, named for its outcome, with one Task per PR.
Reuse existing Projects. Cite file/line or release-note evidence, explain the change,
why it matters, and say how to verify it.

Always update Goal status before the tool limit: date, latest Agno release reviewed,
checks completed and what to check next, even if the scan is incomplete.
"""

goals = [
    Goal(
        id="this-agentos",
        name="AgentOS maintenance",
        objective="Keep this AgentOS current, secure and working.",
        sources=[
            Source(type="website", reference="https://github.com/agno-agi/agno/releases"),
            Source(type="git", reference=str(Path(__file__).resolve().parents[1])),
            *([Source(type="git", reference=REPOSITORY.url)] if REPOSITORY is not None else []),
        ],
        routines=[
            # This routine runs on Agno's default routine executor: `miniagent`.
            Routine(
                name="agentos-maintenance",
                # Mondays at 09:00 UTC.
                cron_expr="0 9 * * 1",
                instructions=MAINTENANCE,
                enabled=False,
                auto_accept=False,
            ),
        ],
    ),
]
