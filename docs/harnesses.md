# Enable coding engineers

Claude and Codex engineers are disabled by default. Enable only the ones you need
in `app/main.py`. For a public deployment, complete JWT setup first.

## Enable in code

Import the factories you want:

```python
from agents.engineers import create_claude_engineer, create_codex_engineer
```

Add their results to the existing `AgentOS` agent list, preserving your other agents:

```python
agents=[
    # Keep your application agents here.
    create_claude_engineer(),
    create_codex_engineer(),
],
```

Claude needs `ANTHROPIC_API_KEY`; Codex uses `OPENAI_API_KEY`. Add credentials to
`.env` locally or your hosted environment settings, then rebuild and deploy.
Adding a key alone does not enable an engineer. Remove its factory call and unused
import to disable it.

With `sandbox_provider()` returning `None`, engineers work directly in the project
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
the engineer to clone your repository into a separate writable directory, create
a feature branch, run checks, push and open a PR. Leave merging and deployment to
you. Verify a small PR before scheduling improvement work.

## Add isolation and scale

When needed, add [sandboxes and checkpoints](sandboxes.md) for isolated work and
recovery. Pass GitHub publishing credentials into the sandbox explicitly through
its provider's `env`; private checkout uses `GITHUB_READ_TOKEN`. Configure the Git
credential helper there too. For multiple API instances, follow [scaling](scaling.md).
