# AgentOS: The self-managing agent platform

The open-source agent platform that runs in your cloud.

**Super Agent** coordinates your agents to deliver outcomes. Ask it to run an agent,
build a new one, investigate a failed run, or organize larger work into Projects
and Tasks. You set direction, approve work, and review results.

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
an agent with you. Already cloned the repo? Ask it to follow `/setup-platform`.

### Or run it yourself

You'll need Git, Docker with Compose, and an OpenAI API key.

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

> Propose a Project to improve our customer support agent. Break it into Tasks for my review.

The **Company** page keeps track of Products, Projects, Tasks, and scheduled Routines.
You can approve work, assign it, review results, and request changes there or through
Super Agent. Products describe ongoing responsibilities; Projects and Tasks organize
specific work; Routines run on a schedule.

This template includes a weekly maintenance Routine that reviews the platform for
relevant Agno updates, security issues, and quality problems. It is **disabled by
default**. Enable it from the Company page to receive proposals for review; automatic
acceptance is off. Scheduled runs use your model API keys.

## Build and improve agents

Build through Super Agent or Studio, or keep your agents in Python. For code changes,
ask your coding agent to follow a skill:

| Task | Skill |
| --- | --- |
| Build an agent | [/create-agent](.agents/skills/create-agent/SKILL.md) |
| Add tools, change behavior, or fix a bug | [/extend-agent](.agents/skills/extend-agent/SKILL.md) |
| Write evals | [/create-evals](.agents/skills/create-evals/SKILL.md) |
| Find weaknesses and improve reliability | [/improve](.agents/skills/improve/SKILL.md) |
| Review the repository before release | [/review-and-improve](.agents/skills/review-and-improve/SKILL.md) |

Python agents go in `agents/` and are registered in [app/main.py](app/main.py).
Set descriptions and quick prompts in [app/config.yaml](app/config.yaml).
[app/registry.py](app/registry.py) supplies tools, models, knowledge, and memory for
agents built in Studio.

### Coding agents

**Claude Engineer** and **Codex Engineer** can read code, make changes, and run commands.
They are off by default. Follow the [harness setup guide](docs/harnesses.md) to enable
them and configure credentials and sandboxes.

Once enabled, ask Super Agent:

> Ask Codex Engineer to review this project and suggest improvements. Don't change any files yet.

Assign Company Tasks to an engineer explicitly when you want it to do the coding.
Without a sandbox, engineers run on the API host with its file and credential access.
[Sandboxes](docs/harnesses.md#sandboxes-and-checkpoints) provide isolated execution
and checkpoint recovery.

## Make it yours

Create an empty private GitHub repository, then point this checkout at it:

```sh
git remote rename origin upstream
git remote add origin https://github.com/YOUR-ORG/YOUR-REPO.git
git push -u origin HEAD
```

Your work now goes to your repository; `upstream` keeps the template available for
updates. If you use sandboxes, also set your repository URL and branch in the
[harness configuration](docs/harnesses.md#sandboxes-and-checkpoints).

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

### Connect Claude, ChatGPT, and coding clients

For browser MCP clients, set `MCP_CONNECT_SECRET` to a random secret in Render and
redeploy. Connect the client to `https://YOUR-DOMAIN/mcp` and enter the secret on
the consent page.

For supported coding clients:

```sh
uvx agno connect --url https://YOUR-DOMAIN
```

## Check your changes

With PostgreSQL running, install [uv](https://docs.astral.sh/uv/) and run:

```sh
./scripts/venv_setup.sh
source .venv/bin/activate
./scripts/validate.sh
python -m evals --tag smoke
```

Validation checks formatting, lint, and types. Smoke evals exercise Super Agent,
spend model calls, and save results in the database. Add cases in
[evals/cases.py](evals/cases.py). Use `./scripts/mcp_check.sh` to check the running
MCP server without a model call.

See [AGENTS.md](AGENTS.md) for development conventions and
[Agno documentation](https://docs.agno.com) for framework guides.
