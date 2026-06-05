from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ...database.db import get_db

router = APIRouter(prefix="/customer-technicians")


class LinkCreate(BaseModel):
    customer_id: UUID
    technician_id: UUID
    place_id: UUID | None = None
    is_primary: bool = False


class PrimaryUpdate(BaseModel):
    customer_id: UUID
    technician_id: UUID
    place_id: UUID | None = None


# 조회
@router.get("/by-customer/{customer_id}", summary="고객사별 정비사 목록 조회", tags=["고객-정비사 연결 / 조회"])
async def get_technicians_by_customer(customer_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        """
        SELECT t.*, ct.place_id, ct.is_primary, ct.created_at AS linked_at
        FROM customer_technician ct
        JOIN technician t ON ct.technician_id = t.id
        WHERE ct.customer_id = $1
        ORDER BY ct.is_primary DESC, ct.place_id NULLS LAST, ct.created_at
        """,
        customer_id,
    )
    return [dict(row) for row in rows]


@router.get("/by-technician/{technician_id}", summary="정비사별 담당 고객사 목록 조회", tags=["고객-정비사 연결 / 조회"])
async def get_customers_by_technician(technician_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        """
        SELECT c.*, ct.place_id, ct.is_primary, ct.created_at AS linked_at
        FROM customer_technician ct
        JOIN customer c ON ct.customer_id = c.id
        WHERE ct.technician_id = $1
        ORDER BY ct.is_primary DESC, ct.created_at
        """,
        technician_id,
    )
    return [dict(row) for row in rows]


# 연결
@router.post("", status_code=201, summary="정비사 ↔ 고객사 연결", tags=["고객-정비사 연결 / 연결"])
async def link_technician(body: LinkCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if not await conn.fetchval("SELECT id FROM technician WHERE id = $1", body.technician_id):
        raise HTTPException(status_code=404, detail=f"technician_id {body.technician_id} 를 찾을 수 없습니다.")
    if body.place_id and not await conn.fetchval("SELECT id FROM place WHERE id = $1", body.place_id):
        raise HTTPException(status_code=404, detail=f"place_id {body.place_id} 를 찾을 수 없습니다.")

    # 동일 (customer, technician, place) 중복 체크
    existing = await conn.fetchval(
        """
        SELECT 1 FROM customer_technician
        WHERE customer_id = $1 AND technician_id = $2
          AND COALESCE(place_id::text, '') = COALESCE($3::text, '')
        """,
        body.customer_id, body.technician_id, body.place_id,
    )
    if existing:
        raise HTTPException(status_code=409, detail="이미 동일한 조건으로 연결된 정비사입니다.")

    if body.is_primary:
        primary_exists = await conn.fetchval(
            "SELECT 1 FROM customer_technician WHERE customer_id = $1 AND is_primary = true",
            body.customer_id,
        )
        if primary_exists:
            raise HTTPException(status_code=409, detail="이미 메인 정비사가 지정되어 있습니다.")

    await conn.execute(
        """
        INSERT INTO customer_technician (customer_id, technician_id, place_id, is_primary)
        VALUES ($1, $2, $3, $4)
        """,
        body.customer_id, body.technician_id, body.place_id, body.is_primary,
    )
    return {
        "linked": True,
        "customer_id": str(body.customer_id),
        "technician_id": str(body.technician_id),
        "place_id": str(body.place_id) if body.place_id else None,
        "is_primary": body.is_primary,
    }


# is_primary 변경
@router.patch("/primary", summary="메인 정비사 변경", tags=["고객-정비사 연결 / 수정"])
async def set_primary_technician(body: PrimaryUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval(
        """
        SELECT 1 FROM customer_technician
        WHERE customer_id = $1 AND technician_id = $2
          AND COALESCE(place_id::text, '') = COALESCE($3::text, '')
        """,
        body.customer_id, body.technician_id, body.place_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="해당 연결을 찾을 수 없습니다.")

    primary_exists = await conn.fetchval(
        "SELECT 1 FROM customer_technician WHERE customer_id = $1 AND is_primary = true AND technician_id != $2",
        body.customer_id, body.technician_id,
    )
    if primary_exists:
        raise HTTPException(status_code=409, detail="이미 메인 정비사가 지정되어 있습니다. 먼저 해제 후 변경해주세요.")

    await conn.execute(
        """
        UPDATE customer_technician SET is_primary = true, updated_at = now()
        WHERE customer_id = $1 AND technician_id = $2
          AND COALESCE(place_id::text, '') = COALESCE($3::text, '')
        """,
        body.customer_id, body.technician_id, body.place_id,
    )
    return {
        "updated": True,
        "customer_id": str(body.customer_id),
        "technician_id": str(body.technician_id),
        "place_id": str(body.place_id) if body.place_id else None,
        "is_primary": True,
    }


# 연결 해제
@router.delete("", summary="정비사 ↔ 고객사 연결 해제", tags=["고객-정비사 연결 / 해제"])
async def unlink_technician(
    customer_id: UUID,
    technician_id: UUID,
    conn=Depends(get_db),
    place_id: UUID | None = None,
):
    result = await conn.execute(
        """
        DELETE FROM customer_technician
        WHERE customer_id = $1 AND technician_id = $2
          AND COALESCE(place_id::text, '') = COALESCE($3::text, '')
        """,
        customer_id, technician_id, place_id,
    )
    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 연결을 찾을 수 없습니다.")
    return {
        "unlinked": True,
        "customer_id": str(customer_id),
        "technician_id": str(technician_id),
        "place_id": str(place_id) if place_id else None,
    }
