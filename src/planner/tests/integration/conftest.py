import asyncio
import os

import asyncpg
import pytest

DEFAULT_DB_URL = "postgresql://planner:planner@localhost:5432/planner"


def _db_available(url: str) -> bool:
    async def _probe() -> None:
        conn = await asyncpg.connect(dsn=url, timeout=2)
        await conn.close()

    try:
        asyncio.run(_probe())
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def db_url() -> str:
    """
    Return the PostgreSQL URL for integration tests.

    The test is skipped when the database is not reachable. Start it with
    `docker compose up -d db`.

    Returns:
        The configured database URL.
    """
    url = os.environ.get("PLANNER_DB_URL", DEFAULT_DB_URL)
    if not _db_available(url):
        pytest.skip(f"PostgreSQL not reachable at {url}")
    return url
