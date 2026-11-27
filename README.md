# AgentOS: The self-managing agent platform

AgentOS is an open-source agent platform that runs in your cloud. It comes with a **Super Agent** that builds agents, coordinates their work, and helps you manage the platform. Ask it to run an agent, create a workflow, or break a larger goal into Projects and Tasks.

Built with [Agno](https://github.com/agno-agi/agno), AgentOS brings together:

- **Agents, teams, and workflows** you build in Python, Studio, or through Super Agent.
- **Memory, knowledge, and storage** backed by your own PostgreSQL database.
- **Permissions, human approvals, and scheduling** for managing work.
- **An API and MCP server** to use your agents in products, Claude, and ChatGPT.

Use the [AgentOS UI](https://os.agno.com) to chat with agents, inspect runs and traces,
and track their work. This template runs locally with Docker and deploys to Render.

## Get started

Give this prompt to your coding agent:

```text
Help me set up my agent platform and build my first agent.

Clone https://github.com/agno-agi/agentos-render into a folder called agent-platform,
cd into it, and follow .agents/skills/setup-platform/SKILL.md.
```

It checks Docker, helps you configure your API key, starts the platform, and builds
an agent with you. If you've already cloned the repo, ask it to run `/setup-platform`.

### Or run it yourself

You'll need Git, Docker, and an OpenAI API key.

```sh
git clone https://github.com/agno-agi/agentos-render agent-platform
cd agent-platform
cp example.env .env
```

Set `OPENAI_API_KEY` in `.env`, then start the platform:

```sh
docker compose up -d --build
```

Once [localhost:8000/docs](http://localhost:8000/docs) loads:

1. Sign in at [os.agno.com](https://os.agno.com).
2. Choose **Connect OS**, select a local connection, and enter `http://localhost:8000`.
3. Open **Super Agent** and tell it what you're working on.

## Put Super Agent to work

Start with a concrete request:

> Build an agent that turns meeting notes into decisions and action items, then run it on these notes: …

Super Agent can use your existing agents or build one for the job. Agents it builds
appear in the Agents list and are available through the API and MCP.

For ongoing work, ask it to create a Project:

> Propose a Project to build a customer support agent. Break it into Tasks for my review.

The **Company** page keeps track of Goals, Projects, Tasks, and scheduled Routines.
You can approve work, assign it, review results, and request changes there or through
Super Agent. Goals describe ongoing responsibilities; Projects and Tasks organize
specific work; Routines run on a schedule.

This template includes a weekly maintenance Routine that reviews the platform for
relevant Agno updates, security issues, and quality problems. It is **disabled by
default**. Enable it from the Company page to receive proposals for review.

## Skills

This repo includes skills for building and managing your agent platform. Ask your
coding agent to follow the relevant skill:

| Task | Skill |
| --- | --- |
| Build an agent | [/create-agent](.agents/skills/create-agent/SKILL.md) |
| Add tools, change behavior, or fix a bug | [/extend-agent](.agents/skills/extend-agent/SKILL.md) |
| Write evals | [/create-evals](.agents/skills/create-evals/SKILL.md) |
| Find weaknesses and improve reliability | [/improve](.agents/skills/improve/SKILL.md) |
| Review the repository before release | [/review-and-improve](.agents/skills/review-and-improve/SKILL.md) |

## Coding agents

This repo comes with **Claude Code** and **Codex** agents. Work with them directly in AgentOS or ask Super Agent to delegate work to them.

They're **off by default**. Follow the [harness setup guide](docs/harnesses.md) to
enable them and configure credentials and sandboxes.

Once enabled, ask Super Agent:

> Ask codex-1 to review this project and suggest improvements. Don't change any files yet.

Without a sandbox, engineers run on the API host with its file and credential access.
[Sandboxes](docs/harnesses.md#sandboxes-and-checkpoints) provide isolated execution
and checkpoint recovery.

### Get a pull request to merge-ready

With both engineers enabled and running in [sandboxes](docs/harnesses.md#sandboxes-and-checkpoints),
the platform has a workflow, **PR to merge-ready**. Ask Super Agent:

> Get this PR to merge-ready: https://github.com/YOUR-ORG/YOUR-REPO/pull/123

It runs in the background and Super Agent reports when it is done. Each round, `claude-1`
and `codex-1` review the pull request at the same time without seeing each other's
review. A triage agent keeps only the real problems a user would hit and drops nitpicks.
If nothing is kept, the pull request is merge-ready. Otherwise `claude-1` fixes the kept
points in its sandbox and the next round reviews the result. It stops after three rounds.

The report gives the result first, then what triage kept and dropped in each round and
why, the fix as a diff, and both reviews in full. The engineers are told never to push or
comment, so the fix stays in the sandbox: apply the diff to the branch yourself. It works
on pull requests of the repository set as `REPOSITORY` in `app/sandbox.py`. The steps are
in `workflows/merge_ready.py`; change them there.

### Run the engineers on your plans

The engineers are `claude-1` and `codex-1`. Each is one worker with one sign-in of its
own. Give an engineer a plan credential and its work is billed to that plan, not to an
API key. Set the credentials in `.env` locally, or in your API host's environment
settings, and restart.

**`claude-1`: `CLAUDE_1_OAUTH_TOKEN`.** On a computer with a browser, run:

```sh
claude setup-token
```

Approve it in the browser with the account whose Claude plan the engineer should use, and
paste the code the browser shows back into the terminal. The terminal then prints the
OAuth token, which starts with `sk-ant-oat01-`. Copy that into `CLAUDE_1_OAUTH_TOKEN`; the
engineer passes it to Claude Code as `CLAUDE_CODE_OAUTH_TOKEN`. The OAuth token lasts one
year and Claude Code does not save it anywhere, so keep it in your secret store.

**`codex-1`: `CODEX_1_AUTH_JSON`.** This is the ChatGPT sign-in (`auth.json`), the way to
put Codex on a ChatGPT plan today. Make a sign-in that only this engineer will use, in
a folder of its own, so it is not the sign-in on your laptop:

```sh
mkdir -p ~/.codex-1
printf 'cli_auth_credentials_store = "file"\n' > ~/.codex-1/config.toml
CODEX_HOME=~/.codex-1 codex login
```

Sign in with the account whose ChatGPT plan the engineer should use. Put the contents of
`~/.codex-1/auth.json` into `CODEX_1_AUTH_JSON`, on one line. In `.env`, wrap it in
single quotes. Then delete `~/.codex-1`, and do not use that sign-in anywhere else:
Codex replaces the tokens in it as it works, and the copy that is left behind stops
working. The platform keeps the current copy, encrypted, in its database, so the setting
only has to be right once. If `codex-1` ever fails to sign in, make a new sign-in the
same way and replace the setting.

**`codex-1` on ChatGPT Enterprise: `CODEX_1_ACCESS_TOKEN`.** A ChatGPT Enterprise
workspace can issue Codex access tokens. If yours does, use one instead of the sign-in:
on the workspace's **Access tokens** page, create a token with the **Codex** scope and an
expiry, and put it in `CODEX_1_ACCESS_TOKEN`. The engineer passes it to Codex as
`CODEX_ACCESS_TOKEN`. Codex does not replace this token as it works, so nothing is stored
and `codex-1` is not limited to one piece of work at a time. When it expires, create a
new one and replace the setting. Set `CODEX_1_AUTH_JSON` or `CODEX_1_ACCESS_TOKEN`, not
both: with both set the engineer is refused at startup. This path has not been run
against a real Enterprise workspace.

Treat these values like passwords. Never commit them or paste them into a chat.

What to expect:

- **A plan credential and an API key are both set.** The plan is used. An engineer with a
  plan credential is never given `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, on the API host
  or in a sandbox, so its work cannot be billed to the key. Your other agents still use
  the keys.
- **Only an API key is set.** The engineer uses the key, billed at API prices.
- **The plan credential is missing, expired or refused.** The engineer's run fails and
  says so. It does not fall back to the API key. A setting that is present but empty
  counts as missing.
- **`codex-1` on a ChatGPT sign-in does one piece of work at a time.** A second Task or queued run
  waits for the first to finish. A direct request while it is working is answered with
  "codex-1 is busy". `claude-1` is not limited.
- **More engineers.** Add `create_claude_engineer(2)` or `create_codex_engineer(2)` in
  `app/main.py` for `claude-2` and `codex-2`. They read `CLAUDE_2_OAUTH_TOKEN` and
  `CODEX_2_AUTH_JSON`. Give each its own sign-in; never share one between two engineers.

## Make this platform yours

Create an empty private GitHub repository, then point this checkout at it:

```sh
git remote rename origin upstream
git remote add origin https://github.com/YOUR-ORG/YOUR-REPO.git
git push -u origin HEAD
```

Your work now goes to your repository; `upstream` keeps the template available for
updates. If you use sandboxes, also set your repository URL and branch in the
[harness configuration](docs/harnesses.md#sandboxes-and-checkpoints).

Engineers push with `GH_TOKEN`. Every engineer run uses this one token, so a push carries
the token's rights, not the rights of the person who asked. Use a
[fine-grained token](docs/harnesses.md#publish-changes-to-github) limited to this one
repository that can push branches and open pull requests, with no admin rights, and
protect `main` so nothing lands without a review.

## Deploy to Render

Ask your coding agent to follow
[/deploy-platform](.agents/skills/deploy-platform/SKILL.md), or:

1. Push your application to GitHub. In Render, choose **New → Blueprint**, connect
   the repository, and select your branch and [render.yaml](render.yaml).
2. Enter `OPENAI_API_KEY` and set `RUNTIME_ENV=dev` for initial setup. The Blueprint
   creates an API service and PostgreSQL database. Review the resources and deploy.
3. Connect the service's HTTPS URL as a **Live** connection at
   [os.agno.com](https://os.agno.com). In **Settings → OS Security**, enable JWT
   authorization and copy the public verification key.
4. Set these values in the Render service's **Environment**, then save and deploy:

   | Variable | Value |
   | --- | --- |
   | `AGENTOS_URL` | Your public HTTPS URL, without a trailing slash. |
   | `JWT_VERIFICATION_KEY` | The full public PEM, with real line breaks. |
   | `RUNTIME_ENV` | `prd`, set together with the verification key. |

Initial setup is unauthenticated; complete the authorization step before using the
platform in production. Verify that the UI connects and `/agents` rejects requests
without a token. Keep `RUNTIME_ENV=prd` on subsequent deployments.

Add any other credentials your agents need directly in Render. Production has its
own database, so add their documents there too. See [example.env](example.env) for
settings and [scaling](docs/scaling.md) before adding API replicas.

## Connect to Claude, ChatGPT, and coding clients

For MCP clients like Claude and ChatGPT, set `MCP_CONNECT_SECRET` to a random secret in Render and redeploy. Connect the client to `https://YOUR-DOMAIN/mcp` and enter the secret on
the consent page.

For supported coding clients:

```sh
uvx agno connect --url https://YOUR-DOMAIN
```

## Local development

Install [uv](https://docs.astral.sh/uv/), then create and activate a virtual environment
from the repository root. If another environment is active, run `deactivate` first.

```sh
./scripts/venv_setup.sh
source .venv/bin/activate
```

The setup script installs the application and development dependencies into `.venv`.
After making changes, format your code and check formatting, lint, and types:

```sh
./scripts/format.sh
./scripts/validate.sh
```

With PostgreSQL running, test Super Agent with the smoke evals. These spend model
calls and save results in the database:

```sh
python -m evals --tag smoke
```

Add cases in [evals/cases.py](evals/cases.py). Use `./scripts/mcp_check.sh` to check
the running MCP server without a model call.

See [AGENTS.md](AGENTS.md) for development conventions and
[Agno documentation](https://docs.agno.com) for framework guides.
