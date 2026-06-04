import asyncpg
from fastapi import Request

async def init_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=2, max_size=10)

async def get_db(request: Request) -> asyncpg.Connection:
    async with request.app.state.pool.acquire() as conn:
        yield conn