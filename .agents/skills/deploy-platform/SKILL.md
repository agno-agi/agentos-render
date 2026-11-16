---
name: deploy-platform
description: Prepare a GitHub repository, deploy AgentOS through a Render Blueprint, configure authentication, and verify the live application. Use for first deployment, redeployment, or production configuration changes.
---

# Deploy the Platform on Render

Help the user deploy their application through the Render dashboard. Prepare the
repository, guide the Blueprint setup, and verify the authenticated application.
Read `AGENTS.md`, [render.yaml](../../../render.yaml), and the application's settings.
Use the current [Render Blueprint docs](https://render.com/docs/infrastructure-as-code)
when dashboard details are uncertain.

## 1. Prepare the GitHub repository

Inspect the Git remotes, branch, and application changes. Reuse the user's repository
if one exists. Otherwise, establish the GitHub owner, repository name, and visibility,
then help create it using the available GitHub integration or `gh repo create`.
Use a private repository unless the user wants it public.

Keep the template remote as `upstream` and make the user's repository `origin`.
Commit the application without credentials or local artifacts and push the
deployment branch; it must include the user's agents, `Dockerfile` and root
`render.yaml`. Help the user give Render's GitHub connection access to the repository.

The Blueprint creates an **AgentOS** project with a **Production** environment.
To use another project name, set `projects[0].name` in `render.yaml` before pushing.

## 2. Deploy the Blueprint

Identify the intended Render workspace and any existing deployment. Reuse its
Blueprint, API service, and database when present; continue to configuration below.
For a new deployment, guide the user through [Render](https://dashboard.render.com):

1. Choose **New → Blueprint** and connect their GitHub repository.
2. Select the deployment branch and root `render.yaml`.
3. Enter `OPENAI_API_KEY` and set `RUNTIME_ENV` to `dev` for initial setup.
4. Review the resources and billing, then choose **Deploy Blueprint**.
5. Wait for the API to become live and copy its public HTTPS URL.

The Blueprint starts one always-on API instance (`1c-2g`: 1 CPU, 2 GB RAM) and a
PostgreSQL 18 database, both in **Virginia**. Initial setup runs without
authentication, so go straight on to securing it. On an existing secured
deployment, keep `RUNTIME_ENV=prd`.

## 3. Configure access

At [os.agno.com](https://os.agno.com/?ref=render-template), create a **Live** connection
using the Render URL. In **Settings → OS Security**, enable **Token-Based
Authorization (JWT)** and copy the public verification key.

In the Render API service's **Environment** settings, configure:

| Variable | Value |
| --- | --- |
| `AGENTOS_URL` | Public HTTPS service URL, without a trailing slash; used by scheduling and MCP OAuth. |
| `JWT_VERIFICATION_KEY` | Complete public PEM, with real line breaks and no surrounding quotes. |
| `RUNTIME_ENV` | `prd`, set together with the verification key to enable production authorization. |
| Model and integration credentials | Values required by the configured agents, such as `ANTHROPIC_API_KEY` for Claude Engineer. |

Have the user enter secrets directly in Render. Preserve existing working settings,
including `JWT_JWKS_FILE` when used for verification. Choose **Save, rebuild, and deploy**,
inspect startup logs, and verify the AgentOS connection once the API is healthy.
`RUNTIME_ENV` uses `sync: false`, so later Blueprint syncs preserve its dashboard value.

For browser MCP access, set `MCP_CONNECT_SECRET` to a securely generated random
secret, save and deploy, then connect the client to `<AGENTOS_URL>/mcp`. The user
enters that secret on the consent page. Preserve an existing secret during updates
and never print credentials. Coding clients can use `uvx agno connect --url <AGENTOS_URL>`.

## 4. Verify the application

Complete setup only after the production redeploy passes these checks:

- `RUNTIME_ENV=prd` is deployed, `/health` succeeds, and `/docs` loads.
- `/agents` rejects unauthenticated requests; an authenticated request succeeds
  within the user's permissions, and the AgentOS UI connects.
- If MCP is configured, an unauthenticated initialization POST rejects access and
  the intended client connects with authentication. A plain `GET /mcp` is not an auth test.

Production has its own database, so add any documents an agent needs there before
testing it. Claim success only for what you verified.

## 5. Hand over

Check that the Blueprint's project shows the API service and the PostgreSQL database
in its **Production** environment. Give the user the live URL, the project and
Blueprint links, and the verification results.

## Updating the application

Push code to the connected branch and check the resulting deploy. If auto-deploy
is disabled, choose **Manual Deploy → Deploy latest commit**. Edit production
settings in **Environment** and save and deploy. Keep infrastructure changes in
`render.yaml`; Blueprint sync can overwrite conflicting dashboard settings.
Preserve the database and saved application state during updates.

When requested, follow [sandboxes](../../../docs/harnesses.md) for hosted coding agent
execution and durable checkpoints, or [scaling](../../../docs/scaling.md) for replicas.
