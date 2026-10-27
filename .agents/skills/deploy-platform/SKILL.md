---
name: deploy-platform
description: Deploy this AgentOS on Render through the dashboard, configure authentication, and verify the live service. Use for first deployment, redeployment, or production configuration changes. Render API scripts are optional.
---

# Deploy the Platform on Render

Use the **Render dashboard by default**. Guide the user through the browser steps
and help with repository preparation, settings, and verification. A Render API
key, the Render CLI, and `.env.production` are not prerequisites for this path.
Use the scripts only when the user chooses API-assisted deployment or already
uses that workflow.

Read `AGENTS.md`, [render.yaml](../../../render.yaml), and the relevant application
settings. The [README deployment scripts](../../../README.md#deploy-in-production)
provide the optional API-assisted path; don't make them a required dashboard step.
Check current [Render Blueprint](https://render.com/docs/infrastructure-as-code)
and [environment-variable](https://render.com/docs/configure-environment-variables)
instructions when UI details are uncertain.

Never print credentials or the MCP connect secret. The JWT verification key is
public and may be shared to complete configuration. Preserve existing settings.

## 1. Prepare the repository and target

- Confirm the intended Render workspace and whether this platform already has a
  Blueprint, API service, and database. Use existing resources when present. A
  failed health check does not mean a service is missing; inspect logs and settings
  before creating anything else.
- Check that the platform, including the user's agents, is committed and pushed
  to their own GitHub repository and branch, with `render.yaml` present. Preserve
  configured remotes. Render's GitHub connection must have access to that repo.
- Identify the model credentials the agents need. Have the user enter secrets
  directly in Render; don't upload the local development `.env` wholesale.
- Start with the template's one always-running API instance and managed
  PostgreSQL. Explain the selected resources and their billing before deployment.
  Keep `RUNTIME_ENV=prd` and the Blueprint's database references intact.

If browser interaction is unavailable, give the next specific dashboard action
and resume when the user supplies the result. Don't claim a click, saved setting,
or deployment succeeded without evidence.

## 2. Create the Blueprint in Render

For a new deployment, guide the user through the [Render dashboard](https://dashboard.render.com):

1. Choose **New → Blueprint** and select their repository.
2. Select the pushed branch and the root `render.yaml`.
3. Enter `OPENAI_API_KEY` when prompted, review the API/database plans, and choose
   **Deploy Blueprint**.
4. Open the API service and copy its public HTTPS URL.

For an existing deployment, use its service and public URL and continue with the
settings below. Don't create another Blueprint to recover from a failed deploy.

The initial service may fail its health check until JWT verification is
configured. Don't disable authorization or wait for a healthy API before
helping the user obtain the key.

## 3. Connect AgentOS and configure the service

1. At [os.agno.com](https://os.agno.com/?ref=render-template), create a **Live**
   connection using the public Render URL.
2. In the connection's **Settings → OS & Security**, enable **Token-Based
   Authorization (JWT)** and copy the public verification key.
3. In the Render API service's **Environment** settings, set:

   | Variable | Value |
   | --- | --- |
   | `AGENTOS_URL` | The public HTTPS service URL, without a trailing slash. Used by scheduling and MCP OAuth. |
   | `JWT_VERIFICATION_KEY` | The complete public PEM, with real line breaks and no surrounding quotes in the dashboard. |
   | Additional model credentials | The keys the configured agents use, such as `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` for Claude Engineer. |

   Preserve an existing working `JWT_JWKS_FILE` configuration if the deployment
   uses a JWKS file available on the server instead. Keep authentication enabled.
4. Choose **Save, rebuild, and deploy**, inspect startup logs, and return to
   AgentOS to complete the connection once the service is healthy.

For browser MCP connections, have the user generate a long random secret using
their password manager or a secure local method and set `MCP_CONNECT_SECRET` in
Render. Keep an existing secret unless rotation is requested. Choose **Save and
deploy** to apply it. This enables the template's MCP OAuth flow; the client uses
`<AGENTOS_URL>/mcp` and the secret on its consent page.

Production PostgreSQL is separate from local PostgreSQL. When checking a product
agent, ingest its documents into the deployed knowledge base first. Code deploys
do not copy local knowledge records or conversations.

## 4. Verify and hand over

Inspect bounded startup logs and check the public service:

- `/health` succeeds and `/docs` loads.
- `/agents` without a token rejects access; an authenticated request works for
  the caller's permissions, and the AgentOS UI connects.
- When MCP is configured, an unauthenticated initialization POST rejects access.
  With OAuth enabled, check the Bearer challenge and the intended client's
  authenticated connection. A plain `GET /mcp` may serve public metadata and
  does not test authorization.

Report what you actually checked and anything still pending. Agent prompts spend
model calls; name the tests run. Direct engineer runs, HTTP runs, delegation, and
Company Task completion need separate checks before claiming they work.

Give the user the service URL and the dashboard update path:

- **Code:** push to the connected branch and check the resulting deploy, or use
  **Manual Deploy → Deploy latest commit** if automatic deployment is disabled.
- **Settings:** edit **Environment** and choose **Save and deploy**. Removing a
  local variable does not clear its saved Render value.
- **Redeploy:** use **Manual Deploy → Deploy latest commit** on the Deploys page.

For coding clients, `uvx agno connect --url <AGENTOS_URL>` connects to the live
platform; it does not require a Render API key. Preserve saved conversations,
knowledge, schedules, and Company work during updates. Do not remove resources
as deployment cleanup.

## Optional: API-assisted deployment

When the user chooses the scripts, read the README and `scripts/render/` before
running them. This path requires a **Render API key**, Python 3, and OpenSSL.
Create `.env.production` from `example.env` only if it does not exist, remove unused
placeholder credentials, and keep it out of Git.

For an existing dashboard deployment, reconcile the local production settings
with Render first. Preserve the public URL, JWT configuration, MCP secret, model
keys, and Blueprint-managed database values. Set `RENDER_API_KEY` securely and
identify the intended `RENDER_SERVICE_ID` and `RENDER_POSTGRES_ID`. Nonempty
exported `RENDER_*` values override the env file; don't target resources by an
ambiguous name.

- `./scripts/render/up.sh` finishes configuration of a Blueprint-created service;
  it does not create the Blueprint. It reads `.env.production` before `.env`.
- `./scripts/render/env-sync.sh` uploads settings from `.env.production` and triggers
  a deploy. It can overwrite dashboard values, so review the intended changes.
- `./scripts/render/redeploy.sh` deploys the connected source.

Quote multiline PEM values in an env file, unlike a raw dashboard value. Reuse
existing resources and verify the public service as above. If a script fails,
inspect partial changes before retrying.

## Optional: sandboxes and replicas

Configure these only when requested. Follow [docs/sandboxes.md](../../../docs/sandboxes.md)
for `REPOSITORY`, AgentCore, and S3 checkpoints, and [docs/scaling.md](../../../docs/scaling.md)
for Redis and replicas. The API needs no checkpoint disk. Supply private repository
and Bedrock settings explicitly through the sandbox provider's environment.
Verify recovery and shared coordination before claiming those paths work.
