# Scaling limitations

Use one API instance with one Uvicorn worker. This is the supported configuration
for the template. Redis is not included or required.

The API needs no attached disk. PostgreSQL stores saved conversations, Company
records, schedules and the durable queue. Optional [AgentCore and S3](sandboxes.md#aws-agentcore-sandbox)
provide isolated engineering and recovery from the last saved checkpoint.
PostgreSQL does not store engineer checkpoint archives.

Removing the disk requirement does not make every runtime feature work across
multiple instances. Live run events and cancellation currently use process-local
coordination. A request can reach instance A while the durable queue assigns the
run to B. Sticky sessions return the client to A without sharing B's events or
cancellation state. S3 checkpoints do not solve this coordination problem.

MCP uses the framework's transport defaults. Agno generates the internal
scheduler credential automatically. Both are suitable for this single-instance
setup; neither provides shared coordination across instances. PostgreSQL claims
coordinate schedules, but do not establish complete support for multiple API
instances.

Horizontal scaling remains future work: Agno needs a verified coordination path
that does not require Redis before this template can support it. That work must
also verify authentication, schedule retries, engineer recovery and file delivery
across instances and failures. Do not add another infrastructure service as a
workaround. Until then, retain one API instance and size it for the workload.
