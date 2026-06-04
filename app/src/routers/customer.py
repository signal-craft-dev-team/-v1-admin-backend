from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.customer import Customer
from ..database.db import get_db
import asyncpg

router = APIRouter(prefix="/customers")


class CustomerCreate(BaseModel):
    name: str

# 조회
@router.get("", response_model=list[Customer], summary="고객 목록 전체 조회", tags=["고객 관리 / 조회"])
async def get_all_customers(conn=Depends(get_db)):
    rows = await conn.fetch("SELECT * FROM customer ORDER BY created_at DESC")
    return [dict(row) for row in rows]


@router.get("/search", response_model=list[Customer], summary="고객 이름으로 검색", tags=["고객 관리 / 조회"])
async def search_customers_by_name(name: str, conn=Depends(get_db)):
    # 띄어쓰기 제거 후 비교
    rows = await conn.fetch(
        r"""
        SELECT * FROM customer
        WHERE REGEXP_REPLACE(name, '\s+', '', 'g')
            ILIKE REGEXP_REPLACE($1, '\s+', '', 'g')
        ORDER BY created_at DESC
        """,
        f"%{name}%",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")
    return [dict(row) for row in rows]

# 수정
class CustomerUpdate(BaseModel):
    name: str | None = None


@router.patch("/{customer_id}", response_model=Customer, summary="고객 정보 수정", tags=["고객 관리 / 수정"])
async def update_customer(customer_id: UUID, body: CustomerUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM customer WHERE id = $1", customer_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 고객을 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE customer SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        customer_id, *list(updates.values()),
    )
    return dict(row)


# 삭제
@router.delete("/hard", summary="고객 완전 삭제 — 연관 데이터 전체 cascade (Hard Delete)", tags=["고객 관리 / 삭제"])
async def hard_delete_customer(
    conn=Depends(get_db),
    customer_id: UUID | None = None,
    name: str | None = None,
):
    if not customer_id and not name:
        raise HTTPException(status_code=422, detail="id 또는 name 중 하나는 필수입니다.")

    if not customer_id:
        customer_id = await conn.fetchval("SELECT id FROM customer WHERE name = $1", name)
        if not customer_id:
            raise HTTPException(status_code=404, detail="해당 고객을 찾을 수 없습니다.")

    async def try_delete(query: str, *args):
        try:
            await conn.execute(query, *args)
        except asyncpg.UndefinedTableError:
            pass

    async with conn.transaction():
        # 1. 센서 하트비트 / 이벤트
        await try_delete("""
            DELETE FROM sensor_heartbeats WHERE sensor_id IN (
                SELECT es.id FROM edge_sensor es
                JOIN edge_server esrv ON es.server_id = esrv.id
                WHERE esrv.customer_id = $1)""", customer_id)
        await try_delete("""
            DELETE FROM sensor_status_events WHERE sensor_id IN (
                SELECT es.id FROM edge_sensor es
                JOIN edge_server esrv ON es.server_id = esrv.id
                WHERE esrv.customer_id = $1)""", customer_id)

        # 2. 오디오 슬라이스 / 추론 결과
        await try_delete("""
            DELETE FROM audio_slices WHERE recording_id IN (
                SELECT id FROM audio_recordings WHERE customer_id = $1)""", customer_id)
        await try_delete("DELETE FROM inference_results WHERE customer_id = $1", customer_id)

        # 3. 알람 / 설비 상태 이력
        await try_delete("DELETE FROM machine_alerts WHERE customer_id = $1", customer_id)
        await try_delete("""
            DELETE FROM machine_status_history WHERE machine_id IN (
                SELECT id FROM machine WHERE customer_id = $1)""", customer_id)
        await try_delete("""
            DELETE FROM machine_status WHERE machine_id IN (
                SELECT id FROM machine WHERE customer_id = $1)""", customer_id)

        # 4. 서버 로그 / 하트비트
        await try_delete("""
            DELETE FROM config_logs WHERE server_id IN (
                SELECT id FROM edge_server WHERE customer_id = $1)""", customer_id)
        await try_delete("""
            DELETE FROM server_heartbeats WHERE server_id IN (
                SELECT id FROM edge_server WHERE customer_id = $1)""", customer_id)

        # 5. 오디오 녹음 / 다운로드 잡
        await try_delete("DELETE FROM audio_recordings WHERE customer_id = $1", customer_id)
        await try_delete("DELETE FROM zip_download_jobs WHERE customer_id = $1", customer_id)

        # 6. 엣지 센서 / 서버
        await try_delete("""
            DELETE FROM edge_sensor WHERE server_id IN (
                SELECT id FROM edge_server WHERE customer_id = $1)""", customer_id)
        await try_delete("DELETE FROM edge_server WHERE customer_id = $1", customer_id)

        # 7. 설비 / 유저 / 현장 / 고객사 (핵심 — 반드시 성공해야 함)
        await conn.execute("DELETE FROM machine WHERE customer_id = $1", customer_id)
        await conn.execute("DELETE FROM app_user WHERE customer_id = $1", customer_id)
        await conn.execute("DELETE FROM place WHERE customer_id = $1", customer_id)
        result = await conn.execute("DELETE FROM customer WHERE id = $1", customer_id)

    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 고객을 찾을 수 없습니다.")
    return {"deleted": True, "id": str(customer_id), "name": name}


@router.delete("/soft", response_model=Customer, summary="고객 비활성화 (Soft Delete)", tags=["고객 관리 / 삭제"])
async def soft_delete_customer(
    conn=Depends(get_db),
    customer_id: UUID | None = None,
    name: str | None = None,
):
    if not customer_id and not name:
        raise HTTPException(status_code=422, detail="id 또는 name 중 하나는 필수입니다.")

    if customer_id:
        row = await conn.fetchrow(
            "UPDATE customer SET is_active = false, updated_at = now() WHERE id = $1 RETURNING *",
            customer_id,
        )
    else:
        row = await conn.fetchrow(
            "UPDATE customer SET is_active = false, updated_at = now() WHERE name = $1 RETURNING *",
            name,
        )

    if not row:
        raise HTTPException(status_code=404, detail="해당 고객을 찾을 수 없습니다.")
    return dict(row)


# 생성
@router.post("", response_model=Customer, status_code=201, summary="고객 생성", tags=["고객 관리 / 생성"])
async def create_customer(body: CustomerCreate, conn=Depends(get_db)):
    row = await conn.fetchrow(
        """
        INSERT INTO customer (id, name)
        VALUES ($1, $2)
        RETURNING *
        """,
        uuid4(),
        body.name,
    )
    return dict(row)
