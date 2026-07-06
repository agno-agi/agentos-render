"""
AgentOS Schedules
==================
"""

from os import getenv
from typing import Any

from agno.scheduler import ScheduleManager
from agno.utils.log import log_info, log_warning

from db import get_postgres_db


def env_flag(name: str, default: bool) -> bool:
    """Read a boolean env var, accepting 1/true/yes (any casing) as true."""
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes")


def _register(
    manager: ScheduleManager,
    *,
    name: str,
    cron: str,
    endpoint: str,
    payload: dict[str, Any],
    description: str,
) -> None:
    """Create or update one schedule; a failure logs a warning instead of crashing startup."""
    try:
        manager.create(
            name=name,
            cron=cron,
            endpoint=endpoint,
            payload=payload,
            description=description,
            if_exists="update",
        )
    except Exception as exc:
        log_warning(f"schedules: could not register '{name}': {exc}")
    else:
        log_info(f"schedules: registered '{name}'")


def register_schedules() -> None:
    """Register schedules (idempotent and fail-soft).

    The deployment check runs daily by default. Scheduled evals are opt-in because they use model calls.
    To add your own, add an `_register(...)` call below — guard it with an env flag if it should be optional.
    """
    try:
        manager = ScheduleManager(get_postgres_db())
    except Exception as exc:
        log_warning(f"schedules: could not initialize ScheduleManager: {exc}")
        return

    if env_flag("ENABLE_DEPLOY_CHECK", default=True):
        _register(
            manager,
            name="deployment-check",
            cron="0 13 * * *",  # 13:00 UTC daily
            endpoint="/workflows/deployment-check/runs",
            payload={"message": "Scheduled deployment check."},
            description="Daily: verify platform wiring and readiness.",
        )
    else:
        log_info("schedules: deployment-check disabled (ENABLE_DEPLOY_CHECK=False)")

    if env_flag("ENABLE_SCHEDULED_EVALS", default=False):
        _register(
            manager,
            name="run-evals",
            cron="0 14 * * *",  # 14:00 UTC daily
            endpoint="/workflows/run-evals/runs",
            payload={"message": "Scheduled eval run."},
            description="Daily: run the eval suite and report regressions.",
        )
    else:
        log_info("schedules: run-evals disabled (ENABLE_SCHEDULED_EVALS=True to enable)")
