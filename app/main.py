from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .src.config import settings
from .src.database.db import init_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await init_pool(settings.DATABASE_URL)
    yield
    await app.state.pool.close()

# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(
    title="SignalCraft Admin API",
    version="0.0.1",
    description='''운영자용 서버.<br>
                  DB 관리, 유저 관리, 운영자 대시보드 API 등을 제공합니다.''',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ADMIN_ORIGINS,   # 스테이징에선 대시보드 origin 으로 잠그세요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
@app.get("/db-test")
async def db_test():
    async with app.state.pool.acquire() as conn:
        result = await conn.fetchval("SELECT * FROM app_user LIMIT 10;")
    return {"db_test": result}