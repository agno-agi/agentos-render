# ===========================================================================
# Shared runtime
# ===========================================================================
FROM agnohq/python:3.14 AS base

USER root
WORKDIR /app
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system

# GitHub access is enabled by a GH_TOKEN.
# Git and gh are included in agnohq/python:3.14.
RUN git config --system credential.https://github.com.helper '!gh auth git-credential' \
    && git config --system user.name 'AgentOS' \
    && git config --system user.email 'agentos@localhost'

# ===========================================================================
# Sandbox (Docker and AgentCore)
# ===========================================================================
FROM base AS sandbox

ENV HOME=/runtime
WORKDIR /workspace

# sandbox supervisor runs as root; agent commands run as UID 1000.
RUN groupadd --gid 1000 sandbox \
    && useradd --uid 1000 --gid 1000 --home-dir /runtime --no-create-home sandbox

# A sandbox's files are held in memory and count toward its memory limit, so nothing is
# installed at run time: the checks' tools are in the image, and the marker tells
# scripts/venv_setup.sh there is nothing to set up.
RUN uv pip install --system mypy ruff \
    && touch /etc/agentos-sandbox

EXPOSE 8080
ENTRYPOINT ["python", "-I", "-m", "agno.sandbox.agentcore.server", "serve"]
CMD []

# ===========================================================================
# AgentOS (default target)
# ===========================================================================
FROM base AS agentos

# The local API uses the host Docker daemon to manage sibling sandboxes.
COPY --from=docker:29-cli /usr/local/bin/docker /usr/local/bin/docker

ENV PYTHONPATH=/app
COPY . .

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
RUN chmod +x /app/scripts/entrypoint.sh
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Default command (overridden by compose for dev)
# ---------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
