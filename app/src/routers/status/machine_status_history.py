from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.serving import MachineStatusHistory, OperationalState, MachineState
from ...database.db import get_db

router = APIRouter(prefix="/machine-status-history")


class MachineStatusHistoryCreate(BaseModel):
    machine_id: UUID
    operational_state: OperationalState
    operational_score: float | None = None
    current_state: MachineState
    recorded_at: datetime


# 조회
@router.get("/by-machine/{machine_id}", response_model=list[MachineStatusHistory], summary="설비 상태 이력 조회", tags=["ML 결과 / 상태 이력"])
async def get_status_history(
    machine_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            """
            SELECT * FROM machine_status_history
            WHERE machine_id = $1 AND recorded_at BETWEEN $2 AND $3
            ORDER BY recorded_at DESC LIMIT $4
            """,
            machine_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM machine_status_history WHERE machine_id = $1 ORDER BY recorded_at DESC LIMIT $2",
            machine_id, limit,
        )
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=MachineStatusHistory, status_code=201, summary="설비 상태 이력 기록", tags=["ML 결과 / 상태 이력"])
async def create_status_history(body: MachineStatusHistoryCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM machine WHERE id = $1", body.machine_id):
        raise HTTPException(status_code=404, detail=f"machine_id {body.machine_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO machine_status_history (
            id, machine_id, operational_state, operational_score, current_state, recorded_at
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        uuid4(), body.machine_id,
        body.operational_state.value, body.operational_score,
        body.current_state.value, body.recorded_at,
    )
    return dict(row)
