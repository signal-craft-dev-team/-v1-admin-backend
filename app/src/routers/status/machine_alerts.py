from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.serving import MachineAlert, AlertSeverity, AlertStatus
from ...database.db import get_db

router = APIRouter(prefix="/machine-alerts")


class MachineAlertCreate(BaseModel):
    machine_id: UUID
    customer_id: UUID
    severity: AlertSeverity
    title: str
    description: str | None = None
    inference_id: UUID | None = None
    occurred_at: datetime


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[MachineAlert], summary="고객사별 알람 조회", tags=["알람 / 조회"])
async def get_alerts_by_customer(
    customer_id: UUID,
    conn=Depends(get_db),
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=100, le=1000),
):
    conditions = ["customer_id = $1"]
    params: list = [customer_id]

    if status:
        params.append(status.value)
        conditions.append(f"status = ${len(params)}")
    if severity:
        params.append(severity.value)
        conditions.append(f"severity = ${len(params)}")

    params.append(limit)
    query = f"""
        SELECT * FROM machine_alerts
        WHERE {' AND '.join(conditions)}
        ORDER BY occurred_at DESC
        LIMIT ${len(params)}
    """
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


@router.get("/by-machine/{machine_id}", response_model=list[MachineAlert], summary="설비별 알람 조회", tags=["알람 / 조회"])
async def get_alerts_by_machine(
    machine_id: UUID,
    conn=Depends(get_db),
    status: AlertStatus | None = None,
    limit: int = Query(default=100, le=1000),
):
    conditions = ["machine_id = $1"]
    params: list = [machine_id]

    if status:
        params.append(status.value)
        conditions.append(f"status = ${len(params)}")

    params.append(limit)
    query = f"""
        SELECT * FROM machine_alerts
        WHERE {' AND '.join(conditions)}
        ORDER BY occurred_at DESC
        LIMIT ${len(params)}
    """
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=MachineAlert, status_code=201, summary="알람 생성", tags=["알람 / 생성"])
async def create_machine_alert(body: MachineAlertCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM machine WHERE id = $1", body.machine_id):
        raise HTTPException(status_code=404, detail=f"machine_id {body.machine_id} 를 찾을 수 없습니다.")
    if not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if body.inference_id and not await conn.fetchval("SELECT id FROM inference_results WHERE id = $1", body.inference_id):
        raise HTTPException(status_code=404, detail=f"inference_id {body.inference_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO machine_alerts (
            id, machine_id, customer_id, inference_id,
            severity, title, description, occurred_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        uuid4(), body.machine_id, body.customer_id, body.inference_id,
        body.severity.value, body.title, body.description, body.occurred_at,
    )
    return dict(row)
