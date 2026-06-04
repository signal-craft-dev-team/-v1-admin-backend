from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.customer import Technician
from ..database.db import get_db

router = APIRouter(prefix="/technicians")


class TechnicianCreate(BaseModel):
    name: str
    phone: str
    address: str
    customer_id: UUID | None = None
    is_primary: bool = False


class TechnicianUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None


# 조회
@router.get("", response_model=list[Technician], summary="정비사 전체 조회", tags=["정비사 / 조회"])
async def get_all_technicians(conn=Depends(get_db)):
    rows = await conn.fetch("SELECT * FROM technician ORDER BY created_at DESC")
    return [dict(row) for row in rows]


@router.get("/search", response_model=list[Technician], summary="정비사 이름 검색", tags=["정비사 / 조회"])
async def search_technicians_by_name(name: str, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM technician WHERE name ILIKE $1 ORDER BY created_at DESC",
        f"%{name}%",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=Technician, status_code=201, summary="정비사 생성", tags=["정비사 / 생성"])
async def create_technician(body: TechnicianCreate, conn=Depends(get_db)):
    if body.customer_id:
        customer = await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")

    async with conn.transaction():
        technician_id = uuid4()
        row = await conn.fetchrow(
            """
            INSERT INTO technician (id, name, phone, address)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            technician_id,
            body.name,
            body.phone,
            body.address,
        )

        if body.customer_id:
            await conn.execute(
                """
                INSERT INTO customer_technician (customer_id, technician_id, is_primary)
                VALUES ($1, $2, $3)
                """,
                body.customer_id,
                technician_id,
                body.is_primary,
            )

    return dict(row)


# 수정
@router.patch("/{technician_id}", response_model=Technician, summary="정비사 정보 수정", tags=["정비사 / 수정"])
async def update_technician(technician_id: UUID, body: TechnicianUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM technician WHERE id = $1", technician_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 정비사를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    values = list(updates.values())

    row = await conn.fetchrow(
        f"UPDATE technician SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        technician_id, *values,
    )
    return dict(row)


# 삭제
@router.delete("/hard/{technician_id}", summary="정비사 완전 삭제 (Hard Delete)", tags=["정비사 / 삭제"])
async def hard_delete_technician(technician_id: UUID, conn=Depends(get_db)):
    result = await conn.execute("DELETE FROM technician WHERE id = $1", technician_id)
    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 정비사를 찾을 수 없습니다.")
    return {"deleted": True, "id": str(technician_id)}


@router.delete("/soft/{technician_id}", response_model=Technician, summary="정비사 비활성화 (Soft Delete)", tags=["정비사 / 삭제"])
async def soft_delete_technician(technician_id: UUID, conn=Depends(get_db)):
    row = await conn.fetchrow(
        "UPDATE technician SET is_active = false, updated_at = now() WHERE id = $1 RETURNING *",
        technician_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 정비사를 찾을 수 없습니다.")
    return dict(row)
