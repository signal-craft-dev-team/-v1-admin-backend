from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.machine import MachineModel
from ...database.db import get_db

router = APIRouter(prefix="/machine-models")


class MachineModelCreate(BaseModel):
    model_name: str
    manufacturer: str | None = None
    category: str | None = None
    description: str | None = None


# 조회
@router.get("", response_model=list[MachineModel], summary="설비 모델 전체 조회", tags=["설비 모델 / 조회"])
async def get_all_machine_models(conn=Depends(get_db)):
    rows = await conn.fetch("SELECT * FROM machine_model ORDER BY created_at DESC")
    return [dict(row) for row in rows]


@router.get("/search", response_model=list[MachineModel], summary="설비 모델 검색", tags=["설비 모델 / 조회"])
async def search_machine_models(
    conn=Depends(get_db),
    model_name: str | None = None,
    manufacturer: str | None = None,
    category: str | None = None,
):
    if not any([model_name, manufacturer, category]):
        raise HTTPException(status_code=422, detail="model_name, manufacturer, category 중 하나는 필수입니다.")

    conditions = []
    params = []

    if model_name:
        params.append(f"%{model_name}%")
        conditions.append(f"model_name ILIKE ${len(params)}")
    if manufacturer:
        params.append(f"%{manufacturer}%")
        conditions.append(f"manufacturer ILIKE ${len(params)}")
    if category:
        params.append(f"%{category}%")
        conditions.append(f"category ILIKE ${len(params)}")

    query = f"SELECT * FROM machine_model WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
    rows = await conn.fetch(query, *params)

    if not rows:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=MachineModel, status_code=201, summary="설비 모델 생성", tags=["설비 모델 / 생성"])
async def create_machine_model(body: MachineModelCreate, conn=Depends(get_db)):
    row = await conn.fetchrow(
        """
        INSERT INTO machine_model (id, model_name, manufacturer, category, description)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        uuid4(),
        body.model_name,
        body.manufacturer,
        body.category,
        body.description,
    )
    return dict(row)


# 수정
class MachineModelUpdate(BaseModel):
    model_name: str | None = None
    manufacturer: str | None = None
    category: str | None = None
    description: str | None = None


@router.patch("/{model_id}", response_model=MachineModel, summary="설비 모델 수정", tags=["설비 모델 / 수정"])
async def update_machine_model(model_id: UUID, body: MachineModelUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM machine_model WHERE id = $1", model_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 설비 모델을 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE machine_model SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        model_id, *list(updates.values()),
    )
    return dict(row)


# 삭제 (Hard only — is_active 없음)
@router.delete("/hard", summary="설비 모델 삭제 (Hard Delete)", tags=["설비 모델 / 삭제"])
async def hard_delete_machine_model(
    conn=Depends(get_db),
    model_id: UUID | None = None,
    model_name: str | None = None,
):
    if not model_id and not model_name:
        raise HTTPException(status_code=422, detail="id 또는 model_name 중 하나는 필수입니다.")

    if model_id:
        result = await conn.execute("DELETE FROM machine_model WHERE id = $1", model_id)
    else:
        result = await conn.execute("DELETE FROM machine_model WHERE model_name = $1", model_name)

    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 설비 모델을 찾을 수 없습니다.")
    return {"deleted": True, "id": str(model_id) if model_id else None, "model_name": model_name}
