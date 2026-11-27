"""
PR to merge-ready
=================

Takes one pull request of this platform's repository through review rounds until nothing real
is left to fix. Ask Super Agent: "Get this PR to merge-ready: <pull request URL>".

Each round:
1. claude-1 and codex-1 review the pull request at the same time, each in its own sandbox,
   without seeing the other's review.
2. A triage agent keeps only the points that are real problems a user would hit. Nitpicks are dropped.
3. If nothing is kept, the pull request is merge-ready and the workflow stops.
4. Otherwise claude-1 fixes the kept points in its sandbox checkout, and the next round reviews
   the pull request with that fix applied.

It stops after three rounds and returns a plain report. The engineers are told never to push or
comment: the fix stays in the sandbox and is returned as a diff for a person to apply.

The workflow is registered only when both engineers are enabled in app/main.py and run in sandboxes.
"""

# The briefs and instructions below are prose sent to models; they are kept on long lines.
# ruff: noqa: E501

import json
import re
from os import getenv
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen

from agno.agent import Agent
from agno.run import RunContext
from agno.workflow import Condition, Loop, Parallel, Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel, Field

from app.settings import super_agent_model
from db import get_postgres_db

if TYPE_CHECKING:
    from agno.agents.claude import ClaudeAgent
    from agno.agents.codex import CodexAgent

MAX_ROUNDS = 3
# The most of a pull request's diff that is pasted into a brief. The engineers read the rest in their checkout.
DIFF_LIMIT = 60000


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


class KeptPoint(BaseModel):
    title: str = Field(..., description="The problem in one sentence")
    location: str = Field(..., description="File and line, or the function")
    raised_by: str = Field(..., description="Claude, Codex or both")
    why_it_matters: str = Field(..., description="What a user of this code would see go wrong")
    fix: str = Field(..., description="What to change, in one or two sentences")


class DroppedPoint(BaseModel):
    title: str
    raised_by: str
    reason: str = Field(..., description="Why it is dropped: wrong, not caused by this pull request, or a nitpick")


class Triage(BaseModel):
    kept: list[KeptPoint] = Field(default_factory=list, description="Real problems a user would hit")
    dropped: list[DroppedPoint] = Field(default_factory=list)


def create_triage_agent() -> Agent:
    # Triage decides whether the rounds end, so it runs on the stronger model. It keeps no session of
    # its own: its decision is stored with the workflow's run.
    return Agent(
        id="merge-ready-triage",
        name="Review Triage",
        model=super_agent_model(),
        output_schema=Triage,
        instructions=[
            "You are given a pull request and two independent reviews of it.",
            "Decide which review points must be fixed before the pull request merges.",
            "Keep a point only when all three hold: the diff shows it is true; this pull request causes it; and a person using the code would hit it, as a wrong result, an error, lost data, a security hole or a broken public interface.",
            "Drop everything else and say why: style, naming, wording, missing comments, refactors, 'consider' suggestions, more tests for code that works, and problems that were there before this pull request.",
            "Do not nitpick. When unsure whether a point is real, drop it and say what you could not confirm.",
            "Two reviewers raising the same problem is one point.",
            "An empty kept list means the pull request is merge-ready.",
        ],
    )


# ---------------------------------------------------------------------------
# Steps that prepare each brief and record each round
# ---------------------------------------------------------------------------

PULL_REQUEST_URL = re.compile(r"https://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)")
NEVER_PUBLISH = (
    "Never push, never comment on the pull request and never open a pull request. Your work stays in this checkout."
)


def github(path: str, accept: str) -> str:
    """Read from the GitHub API on the API host. A private repository needs GITHUB_READ_TOKEN or GH_TOKEN."""
    headers = {"Accept": accept, "User-Agent": "agentos"}
    token = getenv("GITHUB_READ_TOKEN") or getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request("https://api.github.com" + path, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def read_pull_request(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Read the pull request once, on the API host, and keep it for every later step. Read only."""
    state = run_context.session_state
    assert state is not None
    repository_url = state["repository_url"]
    match = PULL_REQUEST_URL.search(step_input.get_input_as_string() or "")
    if match is None:
        return StepOutput(
            content="Give a GitHub pull request URL, such as https://github.com/owner/name/pull/123.",
            success=False,
            stop=True,
        )
    owner, name, number = match.groups()
    if f"https://github.com/{owner}/{name}".lower() != repository_url.lower():
        return StepOutput(
            content=f"This workflow reviews pull requests of {repository_url} only: that is the repository the engineers check out.",
            success=False,
            stop=True,
        )
    path = f"/repos/{owner}/{name}/pulls/{number}"
    try:
        details = json.loads(github(path, "application/vnd.github+json"))
        diff = github(path, "application/vnd.github.v3.diff")
    except OSError as error:
        return StepOutput(
            content=f"Could not read {match.group(0)} from GitHub: {error}. A private repository needs GITHUB_READ_TOKEN or GH_TOKEN.",
            success=False,
            stop=True,
        )
    if len(diff) > DIFF_LIMIT:
        diff = (
            diff[:DIFF_LIMIT] + f"\n[The diff is cut here, at {DIFF_LIMIT} characters. Read the rest in the checkout.]"
        )
    state["pull_request"] = {
        "url": match.group(0),
        "number": int(number),
        "title": details["title"],
        "description": (details.get("body") or "")[:4000],
        "base": details["base"]["ref"],
        "head_commit": details["head"]["sha"],
        "diff": diff,
    }
    state["rounds"] = []
    state.pop("fix_patch", None)
    return StepOutput(content=f"Read pull request {number}: {details['title']} ({details['head']['sha'][:10]})")


def describe(pr: dict[str, Any]) -> str:
    return (
        f"Pull request: {pr['url']}\nTitle: {pr['title']}\nBase branch: {pr['base']}\nHead commit: {pr['head_commit']}\n\n"
        f"Description:\n{pr['description'] or '(none)'}\n\nDiff:\n```diff\n{pr['diff']}\n```"
    )


def checkout_steps(pr: dict[str, Any]) -> str:
    return (
        "Your checkout is in the current directory. Put the pull request's code in it first, unless it is already there "
        "from an earlier turn:\n"
        f"  git fetch --depth=200 origin {pr['base']} pull/{pr['number']}/head\n"
        f"  git checkout --detach {pr['head_commit']}"
    )


def earlier_points(rounds: list[dict[str, Any]]) -> str:
    """The points triage kept in earlier rounds, one per line."""
    lines = [
        f"- Round {entry['round']}: {point['title']} [{point['location']}]"
        for entry in rounds
        for point in (entry.get("triage") or {}).get("kept") or []
    ]
    return "\n".join(lines) or "- (none)"


def review_brief(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """What both reviewers are asked this round. From the second round on it carries the fix made so far."""
    state = run_context.session_state
    assert state is not None
    pr, rounds = state["pull_request"], state["rounds"]
    rounds.append({"round": len(rounds) + 1})
    brief = [
        f"Review this pull request adversarially. This is review round {len(rounds)} of at most {MAX_ROUNDS}.",
        describe(pr),
        checkout_steps(pr),
    ]
    patch = state.get("fix_patch")
    if patch:
        brief.append(
            "After the earlier review round an engineer changed the pull request. Their whole change since the head commit is "
            f"the patch below. First run `git add -A && git diff --cached {pr['head_commit']}` in your checkout. If it already "
            "shows this same change, your checkout has it: leave it as it is. Otherwise run "
            f"`git reset -q --hard {pr['head_commit']} && git clean -fdq`, save the patch to a file and apply it with "
            "`git apply`. If it does not apply, read it as text.\n"
            f"```diff\n{patch}\n```"
        )
        brief.append(
            "The problems that change was meant to fix:\n"
            + earlier_points(rounds[:-1])
            + "\nThis round, check two things: that each of those problems is really fixed, and that the engineer's change "
            "broke nothing. Do not go over the rest of the pull request again for smaller points."
        )
    brief.append(
        "Look for what would go wrong for a person using this code: wrong results, errors, lost data, security holes, broken "
        "public interfaces, and cases the change misses. Read the code around the diff and run things in the checkout to prove "
        "a point when you can. Leave out style, naming and wording. For each problem give the file and line, what goes wrong, "
        "and how you know. If you find no real problem, say exactly: No real problems found.\n" + NEVER_PUBLISH
    )
    return StepOutput(content="\n\n".join(brief))


def review_text(step_input: StepInput, step_name: str) -> str:
    output = step_input.get_step_output(step_name)
    if output is None:
        return "(no review)"
    if output.success is False:
        return f"(the review failed: {output.error or output.content})"
    return str(output.content or "(empty review)")


def triage_brief(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Record both reviews and hand them to triage with the pull request."""
    state = run_context.session_state
    assert state is not None
    current = state["rounds"][-1]
    current["claude_review"] = review_text(step_input, "Claude review")
    current["codex_review"] = review_text(step_input, "Codex review")
    brief = [describe(state["pull_request"])]
    if state.get("fix_patch"):
        brief.append(
            f"Changes an engineer made after earlier review rounds, on top of the diff above:\n```diff\n{state['fix_patch']}\n```"
        )
        brief.append(
            f"This is round {current['round']}. The engineer's changes were meant to fix these points from earlier rounds:\n"
            + earlier_points(state["rounds"][:-1])
            + "\nIn this round keep a point only when one of these holds: an earlier point is still not fixed; the "
            "engineer's changes broke something; or it is a problem you would block the merge on by itself. "
            "A new, smaller point about the original pull request is dropped: the rounds must end."
        )
    brief.append(f"Review by Claude:\n{current['claude_review']}")
    brief.append(f"Review by Codex:\n{current['codex_review']}")
    return StepOutput(content="\n\n".join(brief))


def kept_points(run_context: RunContext) -> list[dict[str, Any]]:
    rounds = (run_context.session_state or {}).get("rounds") or []
    return (rounds[-1].get("triage") or {}).get("kept") or [] if rounds else []


def record_triage(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Keep what triage decided for this round, so the fix step, the loop and the report can read it."""
    state = run_context.session_state
    assert state is not None
    decision = step_input.previous_step_content
    if not isinstance(decision, Triage):
        return StepOutput(content=f"Triage returned no decision: {decision}", success=False, stop=True)
    state["rounds"][-1]["triage"] = decision.model_dump()
    return StepOutput(content=f"Triage kept {len(decision.kept)} and dropped {len(decision.dropped)}.")


def fix_needed(step_input: StepInput, run_context: RunContext) -> bool:
    return bool(kept_points(run_context))


def fix_brief(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """What the fixing engineer is asked: the kept points and nothing else."""
    state = run_context.session_state
    assert state is not None
    pr = state["pull_request"]
    points = "\n".join(
        f"{index}. {point['title']}\n   Where: {point['location']}\n   Why it matters: {point['why_it_matters']}\n   Fix: {point['fix']}"
        for index, point in enumerate(kept_points(run_context), start=1)
    )
    return StepOutput(
        content=(
            "Fix the review points below in this pull request, and only those. Make the smallest change that fixes each one. "
            "Do not refactor and do not fix anything else.\n\n"
            f"{describe(pr)}\n\n{checkout_steps(pr)}\n\n"
            f"Points to fix:\n{points}\n\n"
            "Do not commit. When you are done, run the tests that cover what you changed if you can, then end your reply with:\n"
            "1. One line per point: what you changed, or why you could not fix it.\n"
            f"2. The exact output of `git add -A && git diff --cached {pr['head_commit']}` in one ```diff block, complete and "
            "unedited. It is handed to the next reviewers as a patch.\n" + NEVER_PUBLISH
        )
    )


def record_fix(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Keep the engineer's report and the patch it printed. The patch is the fixer's whole change since the head commit."""
    state = run_context.session_state
    assert state is not None
    reply = str(step_input.previous_step_content or "")
    patches = re.findall(r"```diff\n(.*?)```", reply, flags=re.DOTALL)
    state["rounds"][-1]["fix_report"] = reply
    if patches:
        state["fix_patch"] = patches[-1]
    return StepOutput(
        content="Recorded the fix." if patches else "The engineer printed no diff; the fix is not recorded."
    )


def nothing_left_to_fix(outputs: list[StepOutput]) -> bool:
    """End the loop when triage kept nothing this round."""
    for output in outputs:
        if output.step_name == "Triage" and isinstance(output.content, Triage):
            return not output.content.kept
    return False


def report(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """The plain report. The result and each round's triage come first, so a reader who sees only the start has the answer."""
    state = run_context.session_state
    assert state is not None
    pr, rounds = state["pull_request"], state["rounds"]
    last = (rounds[-1].get("triage") or {}) if rounds else {}
    if rounds and "triage" in rounds[-1] and not last.get("kept"):
        result = f"Merge-ready after {len(rounds)} round(s): the last triage kept nothing."
    else:
        result = f"Not confirmed merge-ready after {len(rounds)} round(s): the last round's fix has not been reviewed."
    if state.get("fix_patch"):
        result += " The fix below is in the engineer's sandbox only: apply it to the branch yourself."
    else:
        result += " No change was made to the pull request."
    lines = [
        f"# Merge-ready report: {pr['title']}",
        f"{pr['url']} at {pr['head_commit'][:10]}",
        f"\n## Result\n{result} Nothing was pushed or posted.",
    ]
    for entry in rounds:
        triage = entry.get("triage") or {}
        lines.append(f"\n## Round {entry['round']}: what triage kept and dropped")
        for point in triage.get("kept") or []:
            lines.append(
                f"- KEPT ({point['raised_by']}): {point['title']} [{point['location']}]. {point['why_it_matters']}"
            )
        for point in triage.get("dropped") or []:
            lines.append(f"- Dropped ({point['raised_by']}): {point['title']}. {point['reason']}")
        if not triage.get("kept") and not triage.get("dropped"):
            lines.append("- Neither reviewer raised a point.")
    if state.get("fix_patch"):
        lines.append(
            "\n## Final diff\nEverything the fixing engineer changed on top of the pull request's head commit, as the engineer "
            f"printed it.\n```diff\n{state['fix_patch']}```"
        )
    for entry in rounds:
        lines.append(f"\n## Round {entry['round']} in full")
        lines.append(f"\n### Claude's review\n{entry.get('claude_review', '(none)')}")
        lines.append(f"\n### Codex's review\n{entry.get('codex_review', '(none)')}")
        if entry.get("fix_report"):
            lines.append(f"\n### What the fixing engineer reported\n{entry['fix_report']}")
    return StepOutput(content="\n".join(lines))


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


def function_step(name: str, executor: Any) -> Step:
    """A step that runs one of the functions above. Agno passes each the step input and the run context."""
    return Step(name=name, executor=executor)


def create_merge_ready_workflow(claude: ClaudeAgent, codex: CodexAgent) -> Workflow:
    """The workflow, with claude as one reviewer and the fixing engineer and codex as the other reviewer."""
    assert claude.repository is not None
    # Agno's own type hints for Parallel and for a two-argument evaluator are narrower than what it accepts.
    reviews: list[Any] = [Step(name="Claude review", agent=claude), Step(name="Codex review", agent=codex)]
    evaluator: Any = fix_needed
    return Workflow(
        id="pr-to-merge-ready",
        name="PR to merge-ready",
        description=(
            "Give it a pull request URL of this repository. Two engineers review it, triage keeps the real problems, "
            "one engineer fixes them; at most three rounds. Returns a report. Never pushes or comments."
        ),
        db=get_postgres_db(),
        session_state={"repository_url": claude.repository.url},
        steps=[
            function_step("Read pull request", read_pull_request),
            Loop(
                name="Review rounds",
                max_iterations=MAX_ROUNDS,
                end_condition=nothing_left_to_fix,
                steps=[
                    function_step("Review brief", review_brief),
                    Parallel(*reviews, name="Independent reviews"),
                    function_step("Triage brief", triage_brief),
                    Step(name="Triage", agent=create_triage_agent()),
                    function_step("Record triage", record_triage),
                    Condition(
                        name="Fix what triage kept",
                        evaluator=evaluator,
                        steps=[
                            function_step("Fix brief", fix_brief),
                            Step(name="Fix", agent=claude),
                            function_step("Record fix", record_fix),
                        ],
                    ),
                ],
            ),
            function_step("Report", report),
        ],
    )


def merge_ready_workflows(agents: list[Any]) -> list[Any]:
    """The workflow when the first Claude engineer and the first Codex engineer are both enabled and sandboxed.

    Without a sandbox an engineer works in the API host's own checkout, where checking out a pull request
    would replace the running application's files. So the workflow is left out.
    """
    if not agents:
        return []
    from agno.agents.claude import ClaudeAgent
    from agno.agents.codex import CodexAgent

    claude = next((agent for agent in agents if isinstance(agent, ClaudeAgent)), None)
    codex = next((agent for agent in agents if isinstance(agent, CodexAgent)), None)
    if claude is None or codex is None:
        return []
    if any(agent.sandbox is None or agent.repository is None for agent in (claude, codex)):
        return []
    return [create_merge_ready_workflow(claude, codex)]
