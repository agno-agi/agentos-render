# Run more than one API instance

Start with the single-instance Blueprint. Removing the API disk permits scaling,
but does not make process-local execution state shared. PostgreSQL stores saved
conversations, Company records and the durable queue. The settings below cover
live coordination; hosted engineer state additionally needs AgentCore and S3.

## Configure shared state

1. Configure [AgentCore and S3](sandboxes.md#aws-agentcore-sandbox) for engineers.
   Use the same repository configuration and checkpoint bucket/prefix on every
   replica. Direct engineers and local Docker checkpoints are not portable
   across API replicas.
2. Provision a private Redis-compatible service, such as Render Key Value, and
   set `REDIS_URL` in `.env.production` to its internal connection URL. Use a
   dedicated instance/database for this platform. Agno uses it for live event
   streams and cancellation; PostgreSQL continues to store the durable queue.
3. Generate a strong random `AGENTOS_INTERNAL_SERVICE_TOKEN` and save the same
   value on every replica. Without an explicit shared value, each process
   generates its own scheduler credential. Keep the token private.
4. Share the database settings, JWT verification configuration, public
   `AGENTOS_URL` and `MCP_CONNECT_SECRET`. Keep queue timing/retry settings
   uniform. Use the default one Uvicorn worker per container.
5. Upload settings using `./scripts/render/env-sync.sh`, verify one instance,
   then test two instances before increasing further. Leave API disks detached.

The template sets MCP transport to stateless. Conversation continuity still uses
the explicit Agno `session_id` and PostgreSQL. Legacy MCP transport resumption
and server-initiated requests are not supported in this mode; test your clients.

## Verify without sticky sessions

Do not rely on affinity for correctness. A request can reach instance A while
the queue assigns execution to B. Returning the client to A does not give it
access to B's process-local events. An established HTTP stream stays on its
connection, but reconnects can reach a different instance.

Test these paths through different instances and the public endpoint:

- Submit a background run, observe its events and cancel from another instance.
- Continue a saved conversation through another instance; verify ownership checks.
- Initialize MCP and invoke tools across instances; verify OAuth and JWT access.
- Run a due Routine once, inspect its saved result, and repeat through a restart.
  PostgreSQL claims coordinate schedules; failures and expired leases still need
  testing. Do not equate retrying a run with exactly-once external actions.
- Replace an API instance and sandbox, then restore an engineer's saved workspace
  and native session from S3.
- Retrieve generated files and uploaded content through another instance. S3
  checkpoints are not a general artifact hosting service; any local-only file
  delivery must be addressed before relying on that feature across replicas.

Inspect database connection limits and workload concurrency as replicas increase.
Keep one production instance until these checks pass for the features you use.
Local tests do not establish Render load-balancer behavior or AWS recovery.
