# Run coding agents on AgentOS

Your platform comes with Claude Code and Codex wired into AgentOS as **Claude Engineer**
and **Codex Engineer**. Enable them, give them a repository, and chat with them in the
AgentOS UI. They can explore the code, implement features, run checks, and open pull
requests once you configure GitHub access.

Start with this platform's repository: ask an agent to build a new agent, write evals,
or improve an existing one. You can also point the coding agents at another project,
or add a Claude/Codex pair for each repository your team works on.

## Enable a coding agent

The included agents are disabled by default. For a public deployment, complete JWT
setup before enabling them.

1. Add `ANTHROPIC_API_KEY` for Claude or `OPENAI_API_KEY` for Codex to `.env` locally
   or your hosted environment settings.
2. In [app/main.py](../app/main.py), uncomment the matching import from
   `agents.engineers` and factory call in the `agents` list. Keep your other agents.
3. Run `./scripts/format.sh`, rebuild and deploy, then open the agent in AgentOS.

Try:

> Read this project and suggest three improvements to its agents. Don't change any files yet.

[agents/engineers.py](../agents/engineers.py) defines their models and harness options.
To disable an agent, comment out its import and factory call and redeploy.

## Choose your repository

For a first local test, the included agents already work in this platform's checkout.
With no sandbox configured, they run on the API host and can access its files,
commands and environment. Use this mode with trusted users; hosted file changes and
native coding sessions can be lost when the container is replaced.

To give them their own checkout, configure a [Docker or AWS sandbox](#sandboxes-and-checkpoints)
and set `REPOSITORY` in [app/sandbox.py](../app/sandbox.py):

```python
REPOSITORY = Repository("https://github.com/YOUR-ORG/agent-platform", branch="main")
```

Use your copy of this template to have the agents work on the platform itself.
To work on a different project, use that project's URL and branch instead:

```python
REPOSITORY = Repository("https://github.com/YOUR-ORG/website", branch="main")
```

Both included agents use this setting when a sandbox is enabled. Setting the URL
alone does not switch direct execution away from the API folder. For private repos,
provide `GITHUB_READ_TOKEN` through the sandbox's `env` mapping, reading it from your
environment or secret store. [Publishing changes](#publish-changes-to-github) needs
GitHub write permissions too.

## Add agents for more repositories

You can run several Claude and Codex agents on the same platform: a pair for the
platform, another for your website, and another for your backend. Give each agent a
unique ID and its own repository configuration.

The included factories have fixed IDs, so keep one instance of each. For additional
agents, configure a sandbox first, then create `agents/repositories.py`:

```python
from agno.agents.claude import ClaudeAgent
from agno.agents.codex import CodexAgent
from agno.sandbox import Repository

from app.sandbox import sandbox_provider
from db import get_postgres_db

sandbox = sandbox_provider()
if sandbox is None:
    raise ValueError("Configure a sandbox in app/sandbox.py first.")
db = get_postgres_db()


def create_repository_agents(slug: str, url: str, branch: str = "main"):
    repository = Repository(url, branch=branch)
    return [
        ClaudeAgent(
            id=f"{slug}-claude",
            name=f"{slug.title()} Claude",
            model="claude-opus-5-5",
            db=db,
            sandbox=sandbox,
            repository=repository,
            system_prompt={"type": "preset", "preset": "claude_code"},
            permission_mode="acceptEdits",
        ),
        CodexAgent(
            id=f"{slug}-codex",
            name=f"{slug.title()} Codex",
            model="gpt-6.1-sol",
            db=db,
            sandbox=sandbox,
            repository=repository,
            sandbox_mode="workspace-write",
        ),
    ]
```

In `app/main.py`, import `create_repository_agents` from `agents.repositories` and
add these entries to the existing `AgentOS` agent list, preserving your other agents:

```python
agents=[
    # Keep your existing agents here.
    *create_repository_agents("platform", "https://github.com/YOUR-ORG/agent-platform"),
    *create_repository_agents("website", "https://github.com/YOUR-ORG/website"),
],
```

This adds **Platform Claude**, **Platform Codex**, **Website Claude**, and **Website Codex**.
Remove either constructor if you only want one coding agent per repository. Add their
suggested prompts to [app/config.yaml](../app/config.yaml), then format and redeploy.

The pairs can share a sandbox provider and checkpoint store; each agent's conversations
have their own sandbox state. They do not share an in-progress checkout, even when
pointed at the same repository. Use Git commits and PRs to share work, and start a new
conversation when changing an agent's repository. Separate agent IDs do not restrict
which repositories a shared GitHub token can access; scope credentials accordingly.

## Sandboxes and checkpoints

A sandbox gives a coding session its own environment and repository checkout.
Checkpoints save its workspace and native coding session for recovery. Use Docker
for local development or AWS AgentCore for a hosted platform. Follow the steps below
from the repository root.

### Local Docker sandbox

Set `sandbox_provider()` to return `docker_sandbox()`. Update `REPOSITORY` to your
GitHub repository and branch. The sandbox checks out that repository.

Run the API on your computer so it can reach Docker. Install [uv](https://docs.astral.sh/uv/)
and configure `.env` using the [local setup instructions](../README.md#run-locally).
If a Python environment is active, run `deactivate` first.

```sh
docker compose up -d agentos-db
./scripts/venv_setup.sh
docker build --target sandbox --load -t agno-sandbox:local .
docker compose stop agentos-api
RUNTIME_ENV=dev DB_HOST=127.0.0.1 DB_PORT=5432 \
  AGENTOS_URL=http://127.0.0.1:8000 \
  uv run --no-project --env-file .env --with-requirements requirements.txt \
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload \
  --reload-dir agents --reload-dir app --reload-dir db --reload-dir evals
```

Keep that terminal running. From another terminal, check the API's MCP connection:

```sh
MCP_CHECK_HOST=1 ./scripts/mcp_check.sh
```

Checkpoints are saved in `tmp/checkpoints`. Agno passes the coding agents' model credentials
to the sandbox. For a private repository, also supply `GITHUB_READ_TOKEN` through the
provider's `env` mapping. Read its value from your environment or secret store;
never put the token itself in code. Git push credentials need separate configuration.

### AWS AgentCore sandbox

Your API stays on its current host. AgentCore runs the coding sessions, and S3
stores their checkpoints. Run [scripts/aws.py](../scripts/aws.py)
from your computer to prepare these resources:

| Resource | Purpose |
| --- | --- |
| ECR repository | Stores the sandbox Docker image. |
| AgentCore runtime | Runs coding sessions; AWS returns its ARN for your application configuration. |
| Private S3 bucket | Stores workspace and native-session checkpoints. |
| IAM execution role | Lets the runtime pull its image and write logs. |
| Application IAM user | Lets your API call this runtime and access its checkpoint prefix. |

#### 1. Configure and preview

Install Python 3, [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
with AgentCore support, and Docker with ARM64 build support. Configure an AWS profile
with permission to manage CloudFormation, ECR, AgentCore, S3 and IAM in your account.
If your organization uses IAM Identity Center, run `aws configure sso` to set up the profile.

Edit the settings at the top of `scripts/aws.py`:

- `AWS_PROFILE`: your local AWS profile name.
- `EXPECTED_ACCOUNT_ID`: your 12-digit AWS account ID. The script checks it before making changes.
- `AWS_REGION`: defaults to `us-east-1` (Northern Virginia).
- `DEPLOYMENT_NAME`: a stable name for this platform's sandbox resources.
- `BUCKET_NAME`: a globally unique bucket name, or leave empty to derive one from the deployment, account and region.
- `CHECKPOINT_PREFIX`: the path within the bucket for this platform's checkpoints.

These settings contain resource names, never credentials. Preview them:

```sh
scripts/aws.py plan
```

This is an offline summary, not an AWS change set. It creates nothing.
For an SSO profile, log in with `aws sso login --profile YOUR_PROFILE`.

#### 2. Create the resources

```sh
scripts/aws.py apply
```

This creates two CloudFormation stacks, builds and pushes the Dockerfile's `sandbox`
target for ARM64, and waits for the runtime and its default endpoint to become ready.
AWS usage incurs charges. The runtime requires IAM authentication; its public
networking lets the coding agent reach GitHub and model APIs.

Run `apply` again after changing the sandbox image or its dependencies. Keep resource
names and the checkpoint prefix stable. The script refuses unrelated stacks and
storage replacements. If provisioning fails, inspect the named stack's Events in
CloudFormation; a failed stack may need recovery before retrying.

#### 3. Connect your API

The script prints the runtime ARN, bucket, prefix, application user and a ready-to-paste
`sandbox_provider()` function for [app/sandbox.py](../app/sandbox.py).
Set `REPOSITORY` to your GitHub URL and branch, then paste the function. To retrieve
the values again:

```sh
scripts/aws.py status
```

For an API hosted outside AWS, open **IAM → Users** in the AWS console and select
the printed `ApplicationUser`. Under **Security credentials**, create an access key
for an application running outside AWS. Enter it directly in your API host's secret
settings (`Environment` on Render):

| Variable | Value |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | The application's access key ID. |
| `AWS_SECRET_ACCESS_KEY` | Its secret access key. |
| `AWS_DEFAULT_REGION` | The region you selected above. |

The script creates no access keys. Keep the provisioning profile's administrator
credentials on your computer. IAM user keys do not need `AWS_SESSION_TOKEN`; remove
stale session credentials or `AWS_PROFILE` settings from the hosted API.
If your API already has an AWS workload role, grant that role the application user's
scoped policy instead of creating access keys. The sandbox execution role is separate:
it has image and logging permissions, not the API's checkpoint or database access.

Keep your existing `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`; Agno forwards model
credentials to the coding agents. Private checkout needs `GITHUB_READ_TOKEN` supplied
explicitly through the provider's `env` mapping, read from your environment or secret
store. See [GitHub access](#publish-changes-to-github) for publishing changes.

Commit the configuration and redeploy your API, preserving JWT authorization.
No API disk or Docker daemon is required on the host. Use the same checkpoint
bucket/prefix on all replicas of this platform. Keep the bucket private and do not
add a lifecycle rule that expires active checkpoints.

#### 4. Verify recovery

Chat with each enabled coding agent. Have it create a test file and finish the turn
so a checkpoint is saved. Replace the API instance and stop that sandbox session,
then continue the same conversation as the same user. Verify that the file and
native coding session are restored. API startup alone does not prove recovery.

Recovery starts at the last successful checkpoint. Unfinished edits and running
processes are not restored; checkpoints cannot undo external actions such as a push.
Investigate inaccessible checkpoints rather than silently starting a new conversation.

#### Remove the AWS resources

Disable sandbox use in the API and redeploy first. Revoke/delete the application's
access keys in IAM, then delete the `<DEPLOYMENT_NAME>-runtime` stack followed by
`<DEPLOYMENT_NAME>-foundation` in CloudFormation.

S3 checkpoints and ECR images are retained to protect your data. Empty and delete
those resources separately when you no longer need them; CloudWatch logs can also
remain. Retained resources can incur storage charges. There is no automatic
checkpoint-deleting cleanup command.

### Company Tasks

For Company Tasks, configure a Product with a saved Git Source matching the coding
agent's repository. The included pair uses `REPOSITORY.url`; additional agents use
their own repository URLs. Adding an agent does not create a Company Product or Source.
Keep the platform's local Source too. Verify a Company Task through completion
separately from chatting with the agent.

## Publish changes to GitHub

Supply `GH_TOKEN` through your environment settings, scoped to the repository with
Contents and Pull requests read/write permissions. Never commit the token.
The image includes Git. To install the GitHub CLI, add this to the Dockerfile's
base stage before `FROM base AS sandbox`, then rebuild:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*
```

For a sandbox, pass `GH_TOKEN` through the provider's `env` mapping, reading it from
your environment or secret store. Private checkout also needs `GITHUB_READ_TOKEN`.
After changing the Dockerfile, run `scripts/aws.py apply` for
AgentCore, or rebuild the local sandbox image. Updating only the API does not update
the AgentCore image.

Configure `gh auth setup-git --hostname github.com` in the execution environment
and set the Git author identity. A sandbox already has the configured repository
checkout. In direct mode, the deployed API image has no `.git` directory, so clone
your repository into a separate writable directory. Ask the coding agent to make a
small change on a feature branch, run checks, push and open a PR. Leave merging and
deployment to you. Verify that PR before scheduling improvement work.

## Scaling

When you need multiple API instances, follow the [scaling guide](scaling.md) for
Redis and coordination across replicas.
