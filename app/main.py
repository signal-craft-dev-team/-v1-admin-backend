from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .src.config import settings
from .src.database.db import init_pool
from .src.routers.customer import customer, app_user, place, technician, customer_technician
from .src.routers.asset import machine_model, machine
from .src.routers.edge import edge_server, edge_sensor, heartbeats, events
from .src.routers.status import machine_alerts, machine_status, machine_status_history
from .src.routers.ml_result import inference_results
from .src.routers.pipeline import audio_recordings, audio_slices, zip_download_jobs

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

@app.get("/health",tags=["헬스체크"])
async def health():
    return {"status": "ok", "version": app.version}

# customer
app.include_router(customer.router)
app.include_router(app_user.router)
app.include_router(place.router)
app.include_router(technician.router)
app.include_router(customer_technician.router)
# asset
app.include_router(machine_model.router)
app.include_router(machine.router)
# edge
app.include_router(edge_server.router)
app.include_router(edge_sensor.router)
app.include_router(heartbeats.router)
app.include_router(events.router)
# status
app.include_router(machine_alerts.router)
app.include_router(machine_status.router)
app.include_router(machine_status_history.router)
# ml_result
app.include_router(inference_results.router)
# pipeline
app.include_router(audio_recordings.router)
app.include_router(audio_slices.router)
app.include_router(zip_download_jobs.router)
