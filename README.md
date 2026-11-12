# AgentOS: The self-managing agent platform

The open-source agent platform that runs in your cloud and comes with a super agent
that runs it for you.

**Super Agent** is the primary agent on your AgentOS. Tell it what you need. It does
the work itself:

- **Runs** your agents, teams, and workflows.
- **Inspects** the platform: runs, schedules, health, and source.
- **Organizes** larger work as Products, Projects, and Tasks.
- **Builds** agents, teams, and workflows with Platform Builder.

Underneath, AgentOS provides sessions, storage, permissions, human approvals,
scheduling, an API, and MCP. People set direction and review results.

Built with [Agno](https://github.com/agno-agi/agno), this template gives you a working
agent platform that you can run locally or deploy to Render.

Use your agents in:

1. **Your product:** call them through the REST API.
2. **Claude and ChatGPT:** connect through the MCP server.
3. **Slack:** connect a Slack app to talk to Super Agent from your workspace.

Run your platform in your own cloud and keep your data in your own PostgreSQL database.
Use the [AgentOS UI](https://os.agno.com) to review conversations, inspect traces,
manage knowledge, and track your agents' work. Build agents with code, use Studio,
or chat with Super Agent.

## Get started

Give this prompt to your coding agent:

```text
Help me set up my agent platform and build my first agent.

Clone https://github.com/agno-agi/agentos-render into a folder called agent-platform,
cd into it, and follow .agents/skills/setup-platform/SKILL.md.
```

It checks Docker, helps you add your API key, starts the platform, and walks you
through building your first agent. Already cloned the repo? Ask your coding agent
to run the `/setup-platform` skill.

## Coding agents

The platform includes **Claude Engineer** and **Codex Engineer**, disabled by default.
They can read code, make changes, and run commands. Enable them in `app/main.py`.
Follow the [harness setup guide](docs/harnesses.md) for the steps.

Once enabled, chat with a coding agent in AgentOS or ask Super Agent to use one:

> Ask Codex Engineer to review this project and suggest improvements. Don't change any files yet.

For Company work, a person accepts a Task on an engineer: "Accept it for Codex Engineer."
Mini Agent will not run a sandboxed engineer.

Without a sandbox, coding agents run on the API host with its file and credential
access. For isolation and checkpoint recovery, set up a
[sandbox](docs/harnesses.md#sandboxes-and-checkpoints): Docker locally, AgentCore
with S3 when deployed.

## Run locally

You'll need Git, Docker with Compose, and an OpenAI API key.
Make sure Docker is running, then run the commands below in your terminal.

### 1. Start the platform

```sh
git clone https://github.com/agno-agi/agentos-render agent-platform
cd agent-platform
cp example.env .env
```

Open `.env` and set `OPENAI_API_KEY`, then start the platform:

```sh
docker compose up -d --build
```

The first build can take a few minutes. When it's ready, open
[http://localhost:8000/docs](http://localhost:8000/docs) to see the API.

Check that AI apps can connect through MCP:

```sh
./scripts/mcp_check.sh
```

The check should report `9 tools; required tools available`.

### 2. Connect the UI

1. Open [os.agno.com](https://os.agno.com) and sign in.
2. Choose **Connect OS**, select a local connection, and enter `http://localhost:8000`.
3. Name it **Local AgentOS**, then open the chat for **Super Agent**.

### 3. Put Super Agent to work

Tell Super Agent what your company does and what you are working on, then ask for
something. For example:

> Build an agent that turns meeting notes into decisions and action items, then run it on these notes: …

Super Agent answers directly, runs the agents you have, and builds one when none fits.
Refresh the Agents list to see what it built. For a larger outcome, ask it to plan the
work as a Project and Tasks. You approve, accept and review them in the chat, each with
one confirmation, or on the **Company** page.

## Build and improve your agents

You can keep working through Super Agent, use Studio, or edit Python files in this repo.
The repo includes instructions, called skills, for common coding tasks.
Ask your coding agent to follow the relevant skill:

| What you want to do | Skill |
| --- | --- |
| Build an agent | [/create-agent](.agents/skills/create-agent/SKILL.md) |
| Add a tool, change behavior, or fix a bug | [/extend-agent](.agents/skills/extend-agent/SKILL.md) |
| Write tests for your agent's answers | [/create-evals](.agents/skills/create-evals/SKILL.md) |
| Harden an agent with simulations and targeted fixes | [/improve](.agents/skills/improve/SKILL.md) |
| Check the repo before sharing or releasing it | [/review-and-improve](.agents/skills/review-and-improve/SKILL.md) |

If you write an agent in Python, put it in `agents/` and add it to
[app/main.py](app/main.py) so the platform can run it. Set its description and
suggested prompts in [app/config.yaml](app/config.yaml). To make a tool or model
available in Studio, add it to [app/registry.py](app/registry.py).

You can give agents documents to search, a notebook to keep notes, and memory
to remember each user.

## Company

CompanyOS organizes the work you delegate to agents. A Product defines an ongoing
area of responsibility, a Project groups related work toward a goal, and a Task
describes a specific job to complete. Routines give agents instructions to carry
out on a schedule.

Agents propose work and you decide. Ask Super Agent to approve a Project, accept a
Task, complete it or send it back. Each decision asks you for one confirmation. The
**Company** page in the AgentOS UI shows the same work.

- **Who does the work:** a Task you accept without naming an agent runs on Mini Agent,
  a built-in agent that only runs Company Tasks and Routines. A Routine only proposes work.
- **When it starts:** an accepted Task starts when you ask Super Agent to start it, or at
  the next hourly automation run, whichever comes first.
- **Changing finished work:** to change a finished Task, reply in the chat where it was
  started, or name the Task. One confirmation sends it back and restarts it.
- **Files:** Super Agent keeps what the company knows in one file tree: `wiki/` for agreed
  direction, `products/` for each Product's brief and status, `tasks/` for what each Task
  was given and produced, and `notes/` for its own notes. Everyone who uses this AgentOS
  shares `notes/`. A change to `wiki/` asks you for a confirmation.

This template includes an `AgentOS` Product for keeping the platform current,
secure and working, with a review Routine scheduled for Mondays at 09:00 UTC. The
Routine is disabled by default, with auto-accept off; enable it from the Company page
in the AgentOS UI. It reads the code and Agno release notes, then proposes Projects and
Tasks for upgrades, security problems and inconsistencies. Most runs propose nothing.
Approve a proposed Project before you accept its Tasks.

With auto-accept on, the hourly automation run approves the Routine's Projects, accepts
and runs their Tasks, and leaves the finished work for you to review. Ask Super Agent to
turn auto-accept on or off for a Routine.

Scheduled reviews use your model API keys and incur usage costs. Check the saved
schedule and run history in Company to see when a review will run and what it did.

[app/company.py](app/company.py) sets the initial review instructions and schedule.
Once they're saved in the database, update the saved Routine to change them;
editing the Python file alone won't change an existing Routine.

## Make it yours

To save your work in your own GitHub repository, create an empty private repo.
From a fresh clone of this template, run the commands below with your repo URL.
This makes `origin` your repo and keeps the original template as `upstream`:

```sh
git remote rename origin upstream
git remote add origin https://github.com/YOUR-ORG/YOUR-REPO.git
git push -u origin HEAD
```

Future pushes go to your repository. You can still fetch updates from `upstream`
and review them before merging.

If you use sandboxes, also set the repository URL and branch in
[the sandbox configuration](docs/harnesses.md#sandboxes-and-checkpoints).

## Deploy in production

Ask your coding agent to follow [deploy-platform](.agents/skills/deploy-platform/SKILL.md),
or use the steps below.

### 1. Push your application to GitHub

Create a new GitHub repository, push the branch you want to deploy, and give Render's GitHub connection access to that repository.

### 2. Deploy the Blueprint

In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint**,
connect your repository, and select the deployment branch and root
[render.yaml](render.yaml). Enter `OPENAI_API_KEY` and set `RUNTIME_ENV` to `dev`
for initial setup. Review the resources and billing, then choose **Deploy Blueprint**.
Reuse the existing Blueprint for later updates, keeping `RUNTIME_ENV=prd` once secured.

The Blueprint creates an **AgentOS** project with a **Production** environment,
containing one always-on API instance with 1 CPU and 2 GB RAM (`1c-2g`)
and a managed PostgreSQL 18 database in **Virginia** (`region: virginia`).

Wait for the API service to become live and copy its public HTTPS URL.
It initially runs without authentication. Continue directly to the next step to secure it.

### 3. Configure authentication and credentials

1. Open [os.agno.com](https://os.agno.com), choose **New AgentOS → Connect → Live**,
   enter the Render service URL, and connect.
2. In **Settings → OS Security**, enable **Token-Based Authorization (JWT)**
   and copy the full public verification key.
3. In the Render API service's **Environment** settings, set:

   | Variable | Value |
   | --- | --- |
   | `AGENTOS_URL` | Public HTTPS service URL, without a trailing slash. |
   | `JWT_VERIFICATION_KEY` | Full public PEM, with real line breaks and no surrounding quotes. |
   | `RUNTIME_ENV` | `prd`, set together with the verification key to enable production authorization. |
   | `ANTHROPIC_API_KEY` | Your Anthropic API key, if you use Claude Engineer with API-key authentication. |

4. Choose **Save, rebuild, and deploy**. Review startup logs and verify the
   AgentOS connection once the API is healthy.

`RUNTIME_ENV` is dashboard-managed (`sync: false`), so later Blueprint syncs
preserve your switch to `prd`.

Enter secrets directly in Render and preserve the Blueprint's database settings.
Production has its own database; ingest any documents your deployed agents need.

### 4. Check the deployment

Confirm the redeploy with `RUNTIME_ENV=prd` has completed. Open `/health` and `/docs`
on your public URL, then connect through the AgentOS UI. Check that `/agents` rejects
requests without a token and works with a valid token. Setup is complete after these checks pass.

### Connect your AI apps

For browser MCP clients, generate a random secret with your password manager,
set it as `MCP_CONNECT_SECRET` in Render's **Environment** settings, and save and deploy.
Use your public URL followed by `/mcp` as the connector URL and enter the secret
on the consent page. Preserve the secret during updates.
For a supported coding client, run:

```sh
uvx agno connect --url https://YOUR-DOMAIN
```

Try asking Super Agent about the platform to check that the connection works.

### Update or remove the deployment

- **Code:** push to the connected branch and check the resulting deployment.
  To redeploy manually, choose **Manual Deploy → Deploy latest commit**.
- **Settings:** edit **Environment** and save and deploy.
- **Infrastructure:** update `render.yaml` and sync the Blueprint. A sync can
  overwrite conflicting dashboard settings.
- **Scale:** read [Scaling](docs/scaling.md) before adding API replicas.
- **Removal:** disconnect the Blueprint, then delete its API service and database
  in the dashboard. Disconnecting alone leaves resources running; deleting the
  database destroys its contents. Verify that both resources are gone.

### Upgrade from Agno 3.1

Agno 3.2 replaces the built-in managers with Super Agent (`superagent`). Company
Routines run on Mini Agent (`miniagent`). After you deploy this version:

- Update each saved Routine that ran on a built-in manager, or it fails:
  `PATCH /company/routines/{id}` with `{"executor_type": "agent", "executor_id": "miniagent"}`.
- Update roles, token scopes, and API clients that name an old ID. Startup stops if a
  stored role policy still uses one. Creating, triggering, or cancelling a Routine
  needs `agents:miniagent:run`; reading its runs needs `agents:miniagent:read`.
- Reconnect MCP clients; the `os_manager` tool is now `super_agent`.
- Earlier sessions stay under their old IDs.

## Verify and develop

To check your Python code and test agent responses, install [uv](https://docs.astral.sh/uv/)
and run these commands from the project folder. Keep the local platform running.
If another Python environment is active, run `deactivate` first.

```sh
./scripts/venv_setup.sh
source .venv/bin/activate
./scripts/validate.sh
python -m evals --tag smoke
```

`validate.sh` checks Python formatting, lint rules, and types. The smoke tests ask
Super Agent to explain setup, check platform health, and explain agent memory.
They use your model API keys and save results in the database for review in the UI.
PostgreSQL must be running, even when you only want to list the tests.

Add your own cases in [evals/cases.py](evals/cases.py), or use
[/create-evals](.agents/skills/create-evals/SKILL.md). To save a report, add
`--json-output tmp/evals.json`. To run one case, use `--name CASE_NAME`.

Change dependencies in `pyproject.toml`, then run `./scripts/generate_requirements.sh`.
Commit the updated `requirements.txt` and rebuild the API and any sandbox image you use.
See [AGENTS.md](AGENTS.md) for the code layout and development conventions.

## Configuration

[example.env](example.env) shows the main settings. Start with `OPENAI_API_KEY`;
add the others when you need them. Use `.env` locally and Render's **Environment** settings for deployment.

| Setting | What it's for |
| --- | --- |
| `OPENAI_API_KEY` | Super Agent, embeddings, and Codex Engineer. |
| `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | Claude Engineer. |
| `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` | Connect Super Agent to Slack. Set both. |
| `PARALLEL_API_KEY` | Optional web search key. Without it, search uses Parallel's MCP server without an API key. |
| `JWT_VERIFICATION_KEY` or `JWT_JWKS_FILE` | Check login tokens in production. A JWKS file must be available on the server. |
| `AGENTOS_URL` | Public URL used by scheduled jobs and MCP. Set it in Render. |
| `MCP_CONNECT_SECRET` | Random secret for browser MCP clients. Generate it and set it in Render. |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_DATABASE` | PostgreSQL connection settings. Local Compose and the Render Blueprint configure these for you. |
| `RUNTIME_ENV` | Set `dev` for initial Render setup, then `prd` with the JWT key. Managed in the Render dashboard. Application default: `prd`; local Compose: `dev`. |

## Learn more

- [Agno documentation](https://docs.agno.com)
- [Agno on GitHub](https://github.com/agno-agi/agno)
- [AgentOS UI](https://os.agno.com)
