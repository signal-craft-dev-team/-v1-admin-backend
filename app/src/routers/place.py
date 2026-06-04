from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.customer import Place
from ..database.db import get_db

router = APIRouter(prefix="/places")


class PlaceCreate(BaseModel):
    customer_id: UUID
    name: str
    sub_name: str | None = None
    address: str | None = None
    description: str | None = None


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[Place], summary="고객사별 현장 목록 조회", tags=["현장 관리 / 조회"])
async def get_places_by_customer(customer_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM place WHERE customer_id = $1 ORDER BY created_at DESC",
        customer_id,
    )
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=Place, status_code=201, summary="현장 생성", tags=["현장 관리 / 생성"])
async def create_place(body: PlaceCreate, conn=Depends(get_db)):
    customer = await conn.fetchval(
        "SELECT id FROM customer WHERE id = $1",
        body.customer_id,
    )
    if not customer:
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO place (id, customer_id, name, sub_name, address, description)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        uuid4(),
        body.customer_id,
        body.name,
        body.sub_name,
        body.address,
        body.description,
    )
    return dict(row)


# 수정
class PlaceUpdate(BaseModel):
    name: str | None = None
    sub_name: str | None = None
    address: str | None = None
    description: str | None = None


@router.patch("/{place_id}", response_model=Place, summary="현장 정보 수정", tags=["현장 관리 / 수정"])
async def update_place(place_id: UUID, body: PlaceUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM place WHERE id = $1", place_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 현장을 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE place SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        place_id, *list(updates.values()),
    )
    return dict(row)


# 삭제
@router.delete("/hard", summary="현장 완전 삭제 (Hard Delete)", tags=["현장 관리 / 삭제"])
async def hard_delete_place(customer_id: UUID, place_id: UUID, conn=Depends(get_db)):
    result = await conn.execute(
        "DELETE FROM place WHERE id = $1 AND customer_id = $2",
        place_id, customer_id,
    )
    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 현장을 찾을 수 없습니다.")
    return {"deleted": True, "customer_id": str(customer_id), "place_id": str(place_id)}


@router.delete("/soft", response_model=Place, summary="현장 비활성화 (Soft Delete)", tags=["현장 관리 / 삭제"])
async def soft_delete_place(customer_id: UUID, place_id: UUID, conn=Depends(get_db)):
    row = await conn.fetchrow(
        "UPDATE place SET is_active = false, updated_at = now() WHERE id = $1 AND customer_id = $2 RETURNING *",
        place_id, customer_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 현장을 찾을 수 없습니다.")
    return dict(row)
