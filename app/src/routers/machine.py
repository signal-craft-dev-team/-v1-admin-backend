from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.machine import Machine
from ..database.db import get_db

router = APIRouter(prefix="/machines")


class MachineCreate(BaseModel):
    model_id: UUID
    customer_id: UUID
    place_id: UUID
    machine_code: str
    label: str | None = None
    installed_at: datetime | None = None


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[Machine], summary="고객사별 설비 목록 조회", tags=["설비 / 조회"])
async def get_machines_by_customer(customer_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM machine WHERE customer_id = $1 ORDER BY created_at DESC",
        customer_id,
    )
    return [dict(row) for row in rows]


@router.get("/by-place/{place_id}", response_model=list[Machine], summary="현장별 설비 목록 조회", tags=["설비 / 조회"])
async def get_machines_by_place(place_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM machine WHERE place_id = $1 ORDER BY created_at DESC",
        place_id,
    )
    return [dict(row) for row in rows]


@router.get("/by-model/{model_id}", response_model=list[Machine], summary="설비 모델별 설비 목록 조회", tags=["설비 / 조회"])
async def get_machines_by_model(model_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM machine WHERE model_id = $1 ORDER BY created_at DESC",
        model_id,
    )
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=Machine, status_code=201, summary="설비 생성", tags=["설비 / 생성"])
async def create_machine(body: MachineCreate, conn=Depends(get_db)):
    duplicate = await conn.fetchval(
        "SELECT id FROM machine WHERE customer_id = $1 AND machine_code = $2",
        body.customer_id, body.machine_code,
    )
    if duplicate:
        raise HTTPException(status_code=409, detail=f"machine_code '{body.machine_code}' 는 이미 해당 고객사에 등록된 코드입니다.")

    model = await conn.fetchval("SELECT id FROM machine_model WHERE id = $1", body.model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"model_id {body.model_id} 를 찾을 수 없습니다.")

    customer = await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")

    place = await conn.fetchval("SELECT id FROM place WHERE id = $1", body.place_id)
    if not place:
        raise HTTPException(status_code=404, detail=f"place_id {body.place_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO machine (id, model_id, customer_id, place_id, machine_code, label, installed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        uuid4(),
        body.model_id,
        body.customer_id,
        body.place_id,
        body.machine_code,
        body.label,
        body.installed_at,
    )
    return dict(row)


# 수정
class MachineUpdate(BaseModel):
    model_id: UUID | None = None
    customer_id: UUID | None = None
    place_id: UUID | None = None
    machine_code: str | None = None
    label: str | None = None
    installed_at: datetime | None = None


@router.patch("/{machine_id}", response_model=Machine, summary="설비 정보 수정", tags=["설비 / 수정"])
async def update_machine(machine_id: UUID, body: MachineUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM machine WHERE id = $1", machine_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 설비를 찾을 수 없습니다.")

    if body.model_id:
        if not await conn.fetchval("SELECT id FROM machine_model WHERE id = $1", body.model_id):
            raise HTTPException(status_code=404, detail=f"model_id {body.model_id} 를 찾을 수 없습니다.")
    if body.customer_id:
        if not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
            raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if body.place_id:
        if not await conn.fetchval("SELECT id FROM place WHERE id = $1", body.place_id):
            raise HTTPException(status_code=404, detail=f"place_id {body.place_id} 를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())

    row = await conn.fetchrow(
        f"UPDATE machine SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        machine_id, *values,
    )
    return dict(row)


# 삭제
@router.delete("/hard/{machine_id}", summary="설비 완전 삭제 (Hard Delete)", tags=["설비 / 삭제"])
async def hard_delete_machine(machine_id: UUID, conn=Depends(get_db)):
    result = await conn.execute("DELETE FROM machine WHERE id = $1", machine_id)
    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 설비를 찾을 수 없습니다.")
    return {"deleted": True, "id": str(machine_id)}


@router.delete("/soft/{machine_id}", response_model=Machine, summary="설비 비활성화 (Soft Delete)", tags=["설비 / 삭제"])
async def soft_delete_machine(machine_id: UUID, conn=Depends(get_db)):
    row = await conn.fetchrow(
        "UPDATE machine SET is_active = false, updated_at = now() WHERE id = $1 RETURNING *",
        machine_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 설비를 찾을 수 없습니다.")
    return dict(row)
