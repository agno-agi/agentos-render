# Set up coding engineers

Claude and Codex engineers are disabled by default. Enable either one explicitly
in code with its model credentials. Start with direct execution, add a sandbox
and checkpoints when needed, then add Redis and replicas using the [scaling guide](scaling.md).

Follow [platform setup](../README.md#run-locally) first. Run commands from the repository
root. Codex needs `OPENAI_API_KEY`; Claude needs `ANTHROPIC_API_KEY` (or
`CLAUDE_CODE_OAUTH_TOKEN` for OAuth). Hosted settings belong in your deployment's
secret configuration. The container does not inherit a host Claude login.
Their models are configured in [agents/engineers.py](../agents/engineers.py).

## Enable an engineer in code

Leave `sandbox_provider()` returning `None` to start with direct execution.
For a hosted API, complete JWT setup before enabling engineering access.
Import only the factories you want in `app/main.py`:

```python
from agents.engineers import create_claude_engineer, create_codex_engineer
```

Add their results to the existing `AgentOS(agents=[...])` list, preserving application agents:

```python
agents=[
    # Keep your existing application agents here.
    create_claude_engineer(),
    create_codex_engineer(),
],
```

You can enable either engineer independently. Adding API keys alone enables neither.
To disable one, remove its factory call and unused import, then redeploy. Before removing
an existing engineer, check saved Studio teams, schedules and Company Tasks that reference
its ID; preserve their history and update active references deliberately.

## Direct execution

With no sandbox configured, engineers work in the project directory on the API
host. They can read its files, edit code and run commands with the process's access,
including access to its environment. Start with trusted users and disposable work.
This mode requires no sandbox infrastructure or checkpoint store. On Render, files
and native coding sessions can disappear on restart or redeploy; PostgreSQL retains
platform records, not the working filesystem. Push work you want to keep.

## Publish branches and pull requests

Give the engineer access to the target GitHub repository using `GH_TOKEN` in your
local environment or hosted secret settings. For a fine-grained token, select only
the target repository and grant Contents and Pull requests read/write permissions.
Complete any organization approval your repository requires. Never put tokens in code.

The template image includes Git. To add the GitHub CLI, insert this in the
`Dockerfile` base stage before `FROM base AS sandbox`, then rebuild and deploy:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*
```

Configure [Git authentication](https://cli.github.com/manual/gh_auth_setup-git)
with `gh auth setup-git --hostname github.com`. The CLI reads
[`GH_TOKEN`](https://cli.github.com/manual/gh_help_environment) from the environment.
Set the Git author name and email for the working checkout.

Render's image contains source files but no `.git` directory. Ask the engineer to
clone your repository into a separate writable directory, work on a feature branch,
run checks, push that branch and open a PR. Leave merging and deployment to you.
Do not edit the serving source tree for this workflow. Verify one small PR manually
before scheduling improvements; setup alone does not prove publishing works.

For sandboxes, pass `GH_TOKEN` explicitly through the provider's `env` mapping,
reading it from your secret store. Private checkout additionally uses
`GITHUB_READ_TOKEN`; keep that token read-only. Configure the GitHub credential
helper inside the sandbox too. The provider does not automatically forward the
API host's GitHub credentials. Only expose write access to sessions authorized
to publish changes.

## Add a sandbox and checkpoints

When you want per-session isolation and workspace recovery, configure one of the
providers below. A configured sandbox requires `REPOSITORY`; invalid sandbox
configuration fails instead of falling back to direct execution. Docker uses
local checkpoints; AgentCore uses S3. Neither is required for the direct mode above.

## Choose your repository

In [app/sandbox.py](../app/sandbox.py), set `REPOSITORY` to your own repo and branch:

```python
REPOSITORY = Repository("https://github.com/YOUR-ORG/YOUR-REPO", branch="main")
```

## Local Docker sandbox

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

Checkpoints are saved in `tmp/checkpoints`. Agno passes the engineers' model credentials
to the sandbox. These files are local: deleting them loses that recovery point.
For a private repository, also supply `GITHUB_READ_TOKEN` through the
`env` argument of `docker_sandbox()`. Read its value from your environment or secret store;
never put the token itself in code. For publishing, also configure `GH_TOKEN` and
the credential helper as described above.

## AWS AgentCore sandbox

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

After configuring the provider, redeploy and test both engineers. Save a file,
complete a turn, then replace the API and sandbox and verify that the next turn
restores the saved file and native session. Recovery starts at the last successfully
saved checkpoint; unfinished edits, live processes and external side effects are
not restored. Missing or inaccessible checkpoints must be investigated rather than
silently restarting the engineer conversation. See the [scaling guide](scaling.md)
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

## Company Tasks

Before using a sandbox for Company Tasks, check that the Product's saved Git Source
matches `REPOSITORY.url`. Keep its local source too, so Company can read the files.
Test an engineer run and a Company Task through completion on your deployment;
a successful API startup does not prove either one works.
