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

Preserve the template remote as `upstream` when making the user's repository
`origin`. Review the files to publish, exclude credentials and local artifacts,
commit the application, and push the intended deployment branch. Verify that the
pushed branch includes the user's agents, `Dockerfile`, and root `render.yaml`.
Help the user grant Render's GitHub connection access to this repository.

## 2. Deploy the Blueprint

Identify the intended Render workspace and any existing deployment. Reuse its
Blueprint, API service, and database when present; continue to configuration below.
For a new deployment, guide the user through [Render](https://dashboard.render.com):

1. Choose **New → Blueprint** and connect their GitHub repository.
2. Select the deployment branch and root `render.yaml`.
3. Enter `OPENAI_API_KEY`, review the resources and billing, and choose **Deploy Blueprint**.
4. Open the API service and copy its public HTTPS URL.

Start with the Blueprint's one always-on API instance and managed PostgreSQL.
Keep `RUNTIME_ENV=prd` and the database references intact. The initial API may fail
startup until the JWT verification key is configured; proceed with that setup.

## 3. Configure access

At [os.agno.com](https://os.agno.com/?ref=render-template), create a **Live** connection
using the Render URL. In **Settings → OS & Security**, enable **Token-Based
Authorization (JWT)** and copy the public verification key.

In the Render API service's **Environment** settings, configure:

| Variable | Value |
| --- | --- |
| `AGENTOS_URL` | Public HTTPS service URL, without a trailing slash; used by scheduling and MCP OAuth. |
| `JWT_VERIFICATION_KEY` | Complete public PEM, with real line breaks and no surrounding quotes. |
| Model and integration credentials | Values required by the configured agents, such as `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` for Claude Engineer. |

Have the user enter secrets directly in Render. Preserve existing working settings,
including `JWT_JWKS_FILE` when used for verification. Choose **Save, rebuild, and deploy**,
inspect startup logs, and complete the AgentOS connection once the API is healthy.

For browser MCP access, set `MCP_CONNECT_SECRET` to a securely generated random
secret, save and deploy, then connect the client to `<AGENTOS_URL>/mcp`. The user
enters that secret on the consent page. Preserve an existing secret during updates
and never print credentials. Coding clients can use `uvx agno connect --url <AGENTOS_URL>`.

## 4. Verify and hand over

Check the public deployment:

- `/health` succeeds and `/docs` loads.
- `/agents` rejects unauthenticated requests; an authenticated request succeeds
  within the user's permissions, and the AgentOS UI connects.
- If MCP is configured, an unauthenticated initialization POST rejects access and
  the intended client connects with authentication. A plain `GET /mcp` is not an auth test.

Production has its own database. Ingest any required documents there before testing
knowledge-dependent agents. Report the service URL, checks completed, and pending
steps. Claim success only for behavior actually verified.

## Updating the application

Push code to the connected branch and check the resulting deploy. If auto-deploy
is disabled, choose **Manual Deploy → Deploy latest commit**. Edit production
settings in **Environment** and save and deploy. Keep infrastructure changes in
`render.yaml`; Blueprint sync can overwrite conflicting dashboard settings.
Preserve the database and saved application state during updates.

When requested, follow [sandboxes](../../../docs/sandboxes.md) for hosted engineer
execution and durable checkpoints, or [scaling](../../../docs/scaling.md) for replicas.
