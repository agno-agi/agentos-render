# AgentOS: The Agent Platform That Builds Itself

AgentOS is a durable agent runtime that serves agents over API, MCP, and chat interfaces like Slack.
Build agents for your product, your team, or yourself. Run them in your own cloud,
keep their data in your own database, and manage them from [AgentOS](https://os.agno.com).

Built with [Agno](https://github.com/agno-agi/agno), this template gives you a working
agent platform that you can run locally or deploy to Render.

**Three ways to build agents.**

1. **Use a coding agent.** Open the repo in Claude Code, Codex, or Cursor. The included
   skills help it create, test, and improve your agents.
2. **Describe what you need.** Chat with OS Manager, the built-in agent that helps you
   manage the platform and build new agents.
3. **Use Studio.** Build agents visually in [AgentOS Studio](https://os.agno.com).

**Three ways to use your agents.**

1. **In your product.** Call your agents through the REST API.
2. **In AI apps.** Connect apps such as Claude and ChatGPT through MCP.
3. **In Slack.** Connect a Slack app to talk to OS Manager from your workspace.

The AgentOS UI lets you chat with your agents, review past conversations, and see
the steps an agent took. Your PostgreSQL database stores conversations, memories,
and Company work.

## Get started

Copy this prompt into your coding agent:

```text
Help me set up my agent platform and build my first agent.

Clone https://github.com/agno-agi/agentos-render into a folder called agent-platform,
cd into it, and follow .agents/skills/setup-platform/SKILL.md.
```

It checks Docker, helps you add your API key, starts the platform, and walks you
through building your first agent. Already cloned the repo? Ask your coding agent
to follow [setup-platform](.agents/skills/setup-platform/SKILL.md) in that folder.

Prefer to set it up yourself? Follow the steps below.

## Engineers

The platform includes **Claude Engineer** and **Codex Engineer**. They can read your
code, make changes, and run commands.

Chat with either engineer in AgentOS, or ask OS Manager to use one:

> Ask Codex Engineer to review this project and suggest improvements. Don't change any files yet.

Codex uses the `OPENAI_API_KEY` you added during setup. To use Claude, add
`ANTHROPIC_API_KEY` to `.env`. After changing `.env`, run `docker compose up -d` again.

By default, engineers work in this project's folder. With Docker Compose, they
can change files in your local checkout, including the code serving the platform.
Review those changes before committing them.

For engineers to work in a separate environment, configure a sandbox with your
own repository URL and branch:

- [Local Docker sandbox](docs/sandboxes.md#local-docker-sandbox): run the API on
  your computer and engineering work in a separate Docker container.
- [AWS AgentCore sandbox](docs/sandboxes.md#aws-agentcore-sandbox): run engineering
  work remotely when the platform is deployed. The API host needs AWS credentials
  and an S3 bucket for checkpoints. No disk is attached to the API service.

Both engineers stay available with either setup. Sandboxes are optional and are
not enabled by the default Compose configuration.

## Run locally

You'll need Git, Docker with Compose, an OpenAI API key and an Anthropic API key
for Claude Engineer. Make sure Docker is running.
Run the commands below in a terminal.

### 1. Start the platform

```sh
git clone https://github.com/agno-agi/agentos-render agent-platform
cd agent-platform
cp example.env .env
```

Open `.env` and set `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` so both engineers can
authenticate. For Claude Code OAuth instead, remove `ANTHROPIC_API_KEY` and set
`CLAUDE_CODE_OAUTH_TOKEN`. Then start the platform:

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
3. Name it **Local AgentOS**, then open the chat for **OS Manager**.

### 3. Build your first agent

Tell OS Manager what you want to build. For example:

> Help me build an agent that answers questions about my product. Here's the documentation URL: …

Review what it proposes, then ask it to build and publish the agent.
Refresh the Agents list and try it out. You can chat with your new agent directly
or ask OS Manager to run it for you.

## Build and improve your agents

You can keep working through OS Manager, use Studio, or edit Python files in this repo.
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
to remember each user. Keep a product's documentation in its own knowledge base,
separate from the platform's documents.

## Company

Company organizes ongoing work. A **Product** is what you're working on, a
**Project** groups related work, and a **Task** is one piece of work to complete.
A **Routine** is a set of instructions that can run on a schedule.

This template includes an **AgentOS** Product for improving the platform itself.
To get started, ask OS Manager:

> Review this codebase and recent Agno releases. Suggest the most useful improvements.

It also includes a daily review at **09:00 UTC**. Company Manager reads the code
and Agno release notes, then proposes up to three Tasks for you to review.
The review is instructed to suggest work and leave approval and execution to you.
Automatic acceptance is off.

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
[the sandbox configuration](docs/sandboxes.md#choose-your-repository).

<a id="deploy-in-production"></a>

## Deploy in production

Ask your coding agent to follow [deploy-platform](.agents/skills/deploy-platform/SKILL.md),
or use the steps below.

### 1. Push your application to GitHub

Create or reuse your own GitHub repository and push the application branch you
want to deploy, including `Dockerfile` and `render.yaml`. Your coding agent can
help create the repository and configure the remotes; see [Make it yours](#make-it-yours).
Give Render's GitHub connection access to that repository.

### 2. Deploy the Blueprint

In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint**,
connect your repository, and select the deployment branch and root
[render.yaml](render.yaml). Enter `OPENAI_API_KEY`, review the resources and billing,
and choose **Deploy Blueprint**. Reuse the existing Blueprint for later updates.

The Blueprint creates one always-on API instance and a managed PostgreSQL 18 database
in **Virginia** (`region: virginia`). Confirm that region for both resources.
Keep `RUNTIME_ENV=prd`. Open the API service and copy its public HTTPS URL.
The API may fail startup until you configure authentication in the next step.

### 3. Configure authentication and credentials

1. Open [os.agno.com](https://os.agno.com), choose **Connect OS → Live**, and enter
   the Render service URL.
2. In **Settings → OS & Security**, enable **Token-Based Authorization (JWT)**
   and copy the full public verification key.
3. In the Render API service's **Environment** settings, set:

   | Variable | Value |
   | --- | --- |
   | `AGENTOS_URL` | Public HTTPS service URL, without a trailing slash. |
   | `JWT_VERIFICATION_KEY` | Full public PEM, with real line breaks and no surrounding quotes. |
   | Additional credentials | Keys used by your agents, such as `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` for Claude Engineer. |

4. Choose **Save, rebuild, and deploy**. Review startup logs and complete the
   AgentOS connection once the API is healthy.

Enter secrets directly in Render and preserve the Blueprint's database settings.
Production has its own database; ingest any documents your deployed agents need.

### 4. Check the deployment

Open `/health` and `/docs` on your public URL, then connect through the AgentOS UI.
Check that `/agents` rejects requests without a token and works with a valid token.

### Connect your AI apps

For browser MCP clients, generate a random secret with your password manager,
set it as `MCP_CONNECT_SECRET` in Render's **Environment** settings, and save and deploy.
Use your public URL followed by `/mcp` as the connector URL and enter the secret
on the consent page. Preserve the secret during updates.
For a supported coding client, run:

```sh
uvx agno connect --url https://YOUR-DOMAIN
```

Try asking OS Manager about the platform to check that the connection works.

### Organize your project

Once the application is live, choose **New → Project** in Render, name it after
your application, and create a **Production** environment. Reuse an existing
project if you have one. Select the API service and PostgreSQL database in the
workspace's service list, choose **Move**, and select the project and environment.

Keep the Blueprint connected to manage configuration. Both resources now appear
in your project; subsequent Blueprint syncs preserve this grouping.

### Update or remove the deployment

- **Code:** push to the connected branch and check the resulting deployment.
  To redeploy manually, choose **Manual Deploy → Deploy latest commit**.
- **Settings:** edit **Environment** and save and deploy.
- **Infrastructure:** update `render.yaml` and sync the Blueprint. A sync can
  overwrite conflicting dashboard settings.
- **Removal:** disconnect the Blueprint, then delete its API service and database
  in the dashboard. Disconnecting alone leaves resources running; deleting the
  database destroys its contents. Verify that both resources are gone.

### Sandbox storage

The API service needs no attached disk. Conversations, memories and Company work
are stored in PostgreSQL. Without a sandbox, engineers run inside the API container;
their edited files and native sessions can be lost on redeploy or replacement.
Database conversation history does not reconstruct that working directory.

For durable, isolated engineering, configure [AWS AgentCore and S3](docs/sandboxes.md#aws-agentcore-sandbox).
S3 stores the last saved workspace and native-session checkpoint. Recovery does
not preserve unfinished edits at the instant of a crash or replay external actions
safely. AWS is optional for getting started. Local Docker isolation is also
available in the [sandbox guide](docs/sandboxes.md#local-docker-sandbox).

Before running multiple API instances, follow [Scaling](docs/scaling.md).

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
OS Manager to explain setup, check platform health, and explain agent memory.
They use your model API keys and save results in the database for review in the UI.
PostgreSQL must be running, even when you only want to list the tests.

Add your own cases in [evals/cases.py](evals/cases.py), or use
[/create-evals](.agents/skills/create-evals/SKILL.md). To save a report, add
`--json-output tmp/evals.json`. To run one case, use `--name CASE_NAME`.
Evals use your application's database and workspace; agents can call tools during a test.

Change dependencies in `pyproject.toml`, then run `./scripts/generate_requirements.sh`.
Commit the updated `requirements.txt` and rebuild the API and any sandbox image you use.
See [AGENTS.md](AGENTS.md) for the code layout and development conventions.

## Configuration

[example.env](example.env) shows the main settings. Start with `OPENAI_API_KEY`;
add the others when you need them. Use `.env` locally and Render's **Environment** settings for deployment.

| Setting | What it's for |
| --- | --- |
| `OPENAI_API_KEY` | OS Manager, embeddings, and Codex Engineer. |
| `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | Claude Engineer. |
| `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` | Connect OS Manager to Slack. Set both. |
| `PARALLEL_API_KEY` | Optional web search key. Without it, search uses Parallel's MCP server without an API key. |
| `JWT_VERIFICATION_KEY` or `JWT_JWKS_FILE` | Check login tokens in production. A JWKS file must be available on the server. |
| `AGENTOS_URL` | Public URL used by scheduled jobs and MCP. Set it in Render. |
| `MCP_CONNECT_SECRET` | Random secret for browser MCP clients. Generate it and set it in Render. |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_DATABASE` | PostgreSQL connection settings. Local Compose and the Render Blueprint configure these for you. |
| `RUNTIME_ENV` | `prd` by default. Local Compose uses `dev`, which disables token checks. |

## Learn more

- [Agno documentation](https://docs.agno.com)
- [Agno on GitHub](https://github.com/agno-agi/agno)
- [AgentOS UI](https://os.agno.com)
