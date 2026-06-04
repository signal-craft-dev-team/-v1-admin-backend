from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from signalcraft_models.customer import AppUser
from ..database.db import get_db

router = APIRouter(prefix="/app-users")


class AppUserCreate(BaseModel):
    customer_id: UUID
    email: str
    name: str
    phone: str
    role: str = Field(..., examples=["admin", "manager", "viewer"])


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[AppUser], summary="고객사별 유저 목록 조회", tags=["앱 유저 관리 / 조회"])
async def get_users_by_customer(customer_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM app_user WHERE customer_id = $1 ORDER BY created_at DESC",
        customer_id,
    )
    return [dict(row) for row in rows]


@router.get("/search", response_model=list[AppUser], summary="이메일로 유저 검색", tags=["앱 유저 관리 / 조회"])
async def search_users_by_email(email: str, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM app_user WHERE email ILIKE $1 ORDER BY created_at DESC",
        f"%{email}%",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="해당 이메일의 유저를 찾을 수 없습니다.")
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=AppUser, status_code=201, summary="유저 생성", tags=["앱 유저 관리 / 생성"])
async def create_app_user(body: AppUserCreate, conn=Depends(get_db)):
    customer = await conn.fetchval(
        "SELECT id FROM customer WHERE id = $1",
        body.customer_id,
    )
    if not customer:
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO app_user (id, customer_id, email, name, phone, role)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        uuid4(),
        body.customer_id,
        body.email,
        body.name,
        body.phone,
        body.role,
    )
    return dict(row)


# 수정
class AppUserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    role: str | None = None


@router.patch("/{user_id}", response_model=AppUser, summary="유저 정보 수정", tags=["앱 유저 관리 / 수정"])
async def update_app_user(user_id: UUID, body: AppUserUpdate, conn=Depends(get_db)):
    existing = await conn.fetchval("SELECT id FROM app_user WHERE id = $1", user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE app_user SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        user_id, *list(updates.values()),
    )
    return dict(row)


# 삭제
@router.delete("/hard", summary="유저 완전 삭제 (Hard Delete)", tags=["앱 유저 관리 / 삭제"])
async def hard_delete_app_user(
    conn=Depends(get_db),
    user_id: UUID | None = None,
    email: str | None = None,
):
    if not user_id and not email:
        raise HTTPException(status_code=422, detail="id 또는 email 중 하나는 필수입니다.")

    if user_id:
        result = await conn.execute("DELETE FROM app_user WHERE id = $1", user_id)
    else:
        result = await conn.execute("DELETE FROM app_user WHERE email = $1", email)

    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")
    return {"deleted": True, "id": str(user_id) if user_id else None, "email": email}


@router.delete("/soft", response_model=AppUser, summary="유저 비활성화 (Soft Delete)", tags=["앱 유저 관리 / 삭제"])
async def soft_delete_app_user(
    conn=Depends(get_db),
    user_id: UUID | None = None,
    email: str | None = None,
):
    if not user_id and not email:
        raise HTTPException(status_code=422, detail="id 또는 email 중 하나는 필수입니다.")

    if user_id:
        row = await conn.fetchrow(
            "UPDATE app_user SET is_active = false, updated_at = now() WHERE id = $1 RETURNING *",
            user_id,
        )
    else:
        row = await conn.fetchrow(
            "UPDATE app_user SET is_active = false, updated_at = now() WHERE email = $1 RETURNING *",
            email,
        )

    if not row:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")
    return dict(row)
