from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from ...database.db import get_db

router = APIRouter(prefix="/heartbeats")


class SensorHeartbeatCreate(BaseModel):
    sensor_id: UUID
    recorded_at: datetime


class ServerHeartbeatCreate(BaseModel):
    server_id: UUID
    recorded_at: datetime


# ─────────────────────────────────────────
# sensor_heartbeats
# ─────────────────────────────────────────

@router.post("/sensor", status_code=201, summary="센서 하트비트 기록", tags=["하트비트 / 센서"])
async def create_sensor_heartbeat(body: SensorHeartbeatCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_sensor WHERE id = $1", body.sensor_id):
        raise HTTPException(status_code=404, detail=f"sensor_id {body.sensor_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        "INSERT INTO sensor_heartbeats (id, sensor_id, recorded_at) VALUES ($1, $2, $3) RETURNING *",
        uuid4(), body.sensor_id, body.recorded_at,
    )
    return dict(row)


@router.get("/sensor/by-sensor/{sensor_id}", summary="센서 하트비트 조회", tags=["하트비트 / 센서"])
async def get_sensor_heartbeats(
    sensor_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            "SELECT * FROM sensor_heartbeats WHERE sensor_id = $1 AND recorded_at BETWEEN $2 AND $3 ORDER BY recorded_at DESC LIMIT $4",
            sensor_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM sensor_heartbeats WHERE sensor_id = $1 ORDER BY recorded_at DESC LIMIT $2",
            sensor_id, limit,
        )
    return [dict(row) for row in rows]


# ─────────────────────────────────────────
# server_heartbeats
# ─────────────────────────────────────────

@router.post("/server", status_code=201, summary="서버 하트비트 기록", tags=["하트비트 / 서버"])
async def create_server_heartbeat(body: ServerHeartbeatCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", body.server_id):
        raise HTTPException(status_code=404, detail=f"server_id {body.server_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        "INSERT INTO server_heartbeats (id, server_id, recorded_at) VALUES ($1, $2, $3) RETURNING *",
        uuid4(), body.server_id, body.recorded_at,
    )
    return dict(row)


@router.get("/server/by-server/{server_id}", summary="서버 하트비트 조회", tags=["하트비트 / 서버"])
async def get_server_heartbeats(
    server_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            "SELECT * FROM server_heartbeats WHERE server_id = $1 AND recorded_at BETWEEN $2 AND $3 ORDER BY recorded_at DESC LIMIT $4",
            server_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM server_heartbeats WHERE server_id = $1 ORDER BY recorded_at DESC LIMIT $2",
            server_id, limit,
        )
    return [dict(row) for row in rows]
