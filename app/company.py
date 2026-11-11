"""
CompanyOS
=========
"""

from pathlib import Path

from agno.company import Product, Routine, Source

from app.sandbox import REPOSITORY

# Recommended: enable an engineer in app/main.py, then add a line to these instructions
# naming it as the executor for code changes, for example: "Use codex-engineer for code changes."
MAINTENANCE = """\
Keep this AgentOS current, secure and working. Propose work only for a problem you can
show in this repository, or for a released Agno change that affects code already here.
New features, new tables and refactors are out of scope. Most runs propose nothing.

Read AGENTS.md, the Product status and the open Projects and Tasks first. Then scan, in
this order:

1. Upgrades. Compare the pinned Agno version with the releases since. When a newer
   release exists, propose the upgrade to that version: the changes that touch code in
   this repository, anything that breaks, and the checks that must pass.
2. Security. Look for secrets in the repository, authorization turned off or widened,
   agents holding tools they do not need, and dependencies with known advisories.
3. Quality. Look for agent instructions, tools or configuration that contradict
   AGENTS.md or each other, settings that no longer have any effect, and checks that
   fail or are missing.

For each finding, propose one Project with a small, bounded outcome, named for what is
true when it is done, such as "Upgrade Agno to 3.2.1". Under it, propose one Task for
each pull request the work needs. Most Projects have one Task. Cite the file and line,
or the release note. Say what changes, why it matters and how to verify it. When an
open Project already covers a finding, add to it instead of proposing another.

Finish by updating the Product status with the date, the latest Agno release you
reviewed and what you checked, so the next run starts from there.
"""

products = [
    Product(
        id="this-agentos",
        name="AgentOS",
        purpose="Keep this AgentOS current, secure and working.",
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
