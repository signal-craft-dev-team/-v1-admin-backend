from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.serving import MachineStatus, OperationalState, MachineState
from ...database.db import get_db

router = APIRouter(prefix="/machine-status")


class MachineStatusCreate(BaseModel):
    machine_id: UUID
    operational_state: OperationalState = OperationalState.unknown
    operational_score: float | None = None
    current_state: MachineState = MachineState.unknown
    remaining_score: float | None = None
    last_inference_id: UUID | None = None


# 조회
@router.get("/{machine_id}", response_model=MachineStatus, summary="설비 현재 상태 조회", tags=["설비 상태 / 조회"])
async def get_machine_status(machine_id: UUID, conn=Depends(get_db)):
    row = await conn.fetchrow(
        "SELECT * FROM machine_status WHERE machine_id = $1",
        machine_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 설비의 상태 정보가 없습니다.")
    return dict(row)


# 생성 / 갱신 (upsert — machine_id가 PK이므로)
@router.post("", response_model=MachineStatus, status_code=201, summary="설비 상태 생성 / 갱신 (Upsert)", tags=["설비 상태 / 생성"])
async def upsert_machine_status(body: MachineStatusCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM machine WHERE id = $1", body.machine_id):
        raise HTTPException(status_code=404, detail=f"machine_id {body.machine_id} 를 찾을 수 없습니다.")
    if body.last_inference_id and not await conn.fetchval(
        "SELECT id FROM inference_results WHERE id = $1", body.last_inference_id
    ):
        raise HTTPException(status_code=404, detail=f"inference_id {body.last_inference_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO machine_status (
            machine_id, operational_state, operational_score,
            current_state, remaining_score, last_inference_id
        ) VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (machine_id) DO UPDATE SET
            operational_state   = EXCLUDED.operational_state,
            operational_score   = EXCLUDED.operational_score,
            current_state       = EXCLUDED.current_state,
            remaining_score     = EXCLUDED.remaining_score,
            last_inference_id   = EXCLUDED.last_inference_id,
            updated_at          = now()
        RETURNING *
        """,
        body.machine_id,
        body.operational_state.value,
        body.operational_score,
        body.current_state.value,
        body.remaining_score,
        body.last_inference_id,
    )
    return dict(row)
