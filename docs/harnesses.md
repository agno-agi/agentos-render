# Enable coding agents

Claude and Codex coding agents are disabled by default. Enable only the ones you need
in `app/main.py`. For a public deployment, complete JWT setup first.

## Enable a coding agent

1. Add its credentials to `.env` locally or your hosted environment settings:
   `ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY` for Codex.
2. In `app/main.py`, uncomment its `from agents.engineers import ...` line and
   matching factory call in the `agents` list. Keep your other agents in the list.
3. Run `./scripts/format.sh`, then rebuild and deploy. Chat with the coding agent in AgentOS.

To disable it, comment out both lines and redeploy. Adding a key alone does not
activate a coding agent. Models and harness options live in
[agents/engineers.py](../agents/engineers.py).

With `sandbox_provider()` returning `None`, coding agents work directly in the project
folder with the API process's access to files, commands and environment. Start with
trusted users and one API instance. Files and native coding sessions can be lost
when a hosted container is replaced; PostgreSQL does not restore that filesystem.

## Publish changes to GitHub

Supply `GH_TOKEN` through your environment settings, scoped to the repository with
Contents and Pull requests read/write permissions. Never commit the token.
The image includes Git. To install the GitHub CLI, add this to the Dockerfile's
base stage before `FROM base AS sandbox`, then rebuild:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*
```

Configure `gh auth setup-git --hostname github.com` in the execution environment
and set the Git author identity. The deployed image has no `.git` directory: ask
the coding agent to clone your repository into a separate writable directory, create
a feature branch, run checks, push and open a PR. Leave merging and deployment to
you. Verify a small PR before scheduling improvement work.

## Sandboxes and checkpoints

Sandboxes are optional. They give engineering sessions their own environment and
repository checkout; checkpoints save the workspace and coding session for recovery.
Choose Docker locally or AWS AgentCore when hosted. Follow the setup below from
the repository root after enabling a coding agent.

Pass GitHub publishing credentials into the sandbox explicitly through the provider's
`env`; private checkout uses `GITHUB_READ_TOKEN`. Configure the Git credential helper
there too, as described in [Publish changes to GitHub](#publish-changes-to-github).

### Choose your repository

In [app/sandbox.py](../app/sandbox.py), set `REPOSITORY` to your own repo and branch:

```python
REPOSITORY = Repository("https://github.com/YOUR-ORG/YOUR-REPO", branch="main")
```

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
to the sandbox. These files are local: deleting them loses that recovery point.
For a private repository, also supply `GITHUB_READ_TOKEN` through the
`env` argument of `docker_sandbox()`. Read its value from your environment or secret store;
never put the token itself in code. Git push credentials need separate configuration.

### AWS AgentCore sandbox

Build an ARM64 sandbox image, using your ECR image URL and tag:

```sh
SANDBOX_ECR_IMAGE=YOUR-ECR-URI:YOUR-TAG
docker build --target sandbox --platform linux/arm64 --load -t "${SANDBOX_ECR_IMAGE}" .
```

Push the image to ECR, then create an AgentCore runtime and execution role with your
AWS tools. Use the image's existing entrypoint. Create a private S3 bucket for
checkpoints, then configure [app/sandbox.py](../app/sandbox.py):

```python
def sandbox_provider() -> Sandbox | None:
    return agentcore_sandbox(
        runtime_arn="arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/YOUR-RUNTIME",
        checkpoint_bucket="your-checkpoint-bucket",
        checkpoint_prefix="your-platform/checkpoints/",
    )
```

Set `REPOSITORY` to your repository and branch. Use a distinct prefix per platform
and the same bucket/prefix on every replica of that platform. The bucket must
already exist; the template does not provision AWS resources.

The API host needs AWS access to invoke and stop this runtime and to read/write
its S3 checkpoint prefix. The runtime ARN determines the compute region; set
`AWS_DEFAULT_REGION` to your bucket's region for S3. Use the SDK credential chain
(profile locally, role or securely supplied credentials when hosted).

For S3, grant `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` and
`s3:AbortMultipartUpload` on that prefix. Without appropriate `s3:ListBucket`
permission, S3 can report a missing object as access denied rather than not found.
If you configure
customer-managed KMS encryption, also provide the required key permissions.
Keep the bucket private. Do not expire active checkpoint objects with a bucket
lifecycle rule. Agno retains a bounded number of checkpoints per session.

No API disk or Docker daemon is required. The API uses temporary local files while
transferring archives; S3 is the durable store. API credentials are not automatically
forwarded into the sandbox. Code inside AgentCore can use its execution role, so
give that role only the permissions the engineering work needs, not the API's
production database or checkpoint-store credentials.

After configuring the provider, redeploy and test both coding agents. Save a file,
complete a turn, then replace the API and sandbox and verify that the next turn
restores the saved file and native session. Recovery starts at the last successfully
saved checkpoint; unfinished edits, live processes and external side effects are
not restored. Missing or inaccessible checkpoints must be investigated rather than
silently restarting the coding agent conversation. See the [scaling guide](scaling.md)
before adding API replicas.

To use Claude through Bedrock, pass `CLAUDE_CODE_USE_BEDROCK="1"` and an explicit
`AWS_REGION` in the `env` argument of `agentcore_sandbox()`. Give its execution role
access to the model, and set Claude's model to a supported Bedrock inference profile,
such as `us.anthropic.claude-opus-5-5`:

```python
return agentcore_sandbox(
    runtime_arn="arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/YOUR-RUNTIME",
    checkpoint_bucket="your-checkpoint-bucket",
    checkpoint_prefix="your-platform/checkpoints/",
    env={"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-east-1"},
)
```

These settings are not copied from the host automatically. For a private repository,
supply `GITHUB_READ_TOKEN` through the same mapping, reading it from your secret store.

### Company Tasks

Before using a sandbox for Company Tasks, check that the Product's saved Git Source
matches `REPOSITORY.url`. Keep its local source too, so Company can read the files.
Test a coding agent run and a Company Task through completion on your deployment;
a successful API startup does not prove either one works.

## Scaling

When you need multiple API instances, follow the [scaling guide](scaling.md) for
Redis and coordination across replicas.
