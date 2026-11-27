"""Apply pending Agno database migrations before the API starts.

Run by scripts/entrypoint.sh. A failure is printed and the API still starts:
AgentOS then reports what is pending and POST /databases/all/migrate applies it.
"""

import asyncio
import sys

from agno.db.migrations.manager import MigrationManager

from db import get_postgres_db


def main() -> int:
    try:
        asyncio.run(MigrationManager(get_postgres_db()).up())
    except Exception as exc:
        print(f"Database migration did not finish: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
