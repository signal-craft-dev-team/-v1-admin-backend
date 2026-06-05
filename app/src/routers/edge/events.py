from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.operational import EventType
from ...database.db import get_db

router = APIRouter(prefix="/events")

import json


class SensorStatusEventCreate(BaseModel):
    sensor_id: UUID
    event_type: EventType
    event_log: dict
    occurred_at: datetime


class ConfigLogCreate(BaseModel):
    server_id: UUID
    changed_params: dict
    occurred_at: datetime


# ─────────────────────────────────────────
# sensor_status_events
# ─────────────────────────────────────────

@router.post("/sensor-status", status_code=201, summary="센서 상태 이벤트 기록", tags=["이벤트 / 센서 상태"])
async def create_sensor_status_event(body: SensorStatusEventCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_sensor WHERE id = $1", body.sensor_id):
        raise HTTPException(status_code=404, detail=f"sensor_id {body.sensor_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        "INSERT INTO sensor_status_events (id, sensor_id, event_type, event_log, occurred_at) VALUES ($1, $2, $3, $4, $5) RETURNING *",
        uuid4(), body.sensor_id, body.event_type.value, json.dumps(body.event_log), body.occurred_at,
    )
    return dict(row)


@router.get("/sensor-status/by-sensor/{sensor_id}", summary="센서 상태 이벤트 조회", tags=["이벤트 / 센서 상태"])
async def get_sensor_status_events(
    sensor_id: UUID,
    conn=Depends(get_db),
    event_type: EventType | None = None,
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    conditions = ["sensor_id = $1"]
    params: list = [sensor_id]

    if event_type:
        params.append(event_type.value)
        conditions.append(f"event_type = ${len(params)}")
    if start:
        params.append(start)
        conditions.append(f"occurred_at >= ${len(params)}")
    if end:
        params.append(end)
        conditions.append(f"occurred_at <= ${len(params)}")

    params.append(limit)
    query = f"SELECT * FROM sensor_status_events WHERE {' AND '.join(conditions)} ORDER BY occurred_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# ─────────────────────────────────────────
# config_logs
# ─────────────────────────────────────────

@router.post("/config-logs", status_code=201, summary="설정 변경 이력 기록", tags=["이벤트 / 설정 변경"])
async def create_config_log(body: ConfigLogCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", body.server_id):
        raise HTTPException(status_code=404, detail=f"server_id {body.server_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        "INSERT INTO config_logs (id, server_id, changed_params, occurred_at) VALUES ($1, $2, $3, $4) RETURNING *",
        uuid4(), body.server_id, json.dumps(body.changed_params), body.occurred_at,
    )
    return dict(row)


@router.get("/config-logs/by-server/{server_id}", summary="설정 변경 이력 조회", tags=["이벤트 / 설정 변경"])
async def get_config_logs(
    server_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            "SELECT * FROM config_logs WHERE server_id = $1 AND occurred_at BETWEEN $2 AND $3 ORDER BY occurred_at DESC LIMIT $4",
            server_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM config_logs WHERE server_id = $1 ORDER BY occurred_at DESC LIMIT $2",
            server_id, limit,
        )
    return [dict(row) for row in rows]
