import asyncpg
from pgvector.asyncpg import register_vector
from pathlib import Path

from rag_chatbot.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            init=_init_connection,
        )
    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    await register_vector(conn)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def run_schema() -> None:
    # Install the pgvector extension via a plain connection before creating the
    # pool — register_vector (called for every pool connection) will fail with
    # "unknown type: public.vector" if the extension doesn't exist yet.
    raw = await asyncpg.connect(settings.database_url)
    try:
        await raw.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    finally:
        await raw.close()

    schema_sql = (Path(__file__).parent / "schema.sql").read_text()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Running schema migrations...")
        await run_schema()
        print("Done.")
        await close_pool()

    asyncio.run(main())
