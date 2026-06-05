from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.pipeline import ZipDownloadJob, DataStatus
from ...database.db import get_db

router = APIRouter(prefix="/zip-download-jobs")


class ZipDownloadJobUpdate(BaseModel):
    status: DataStatus | None = None
    download_url: str | None = None
    expires_at: datetime | None = None


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[ZipDownloadJob], summary="고객사별 다운로드 작업 조회", tags=["데이터 파이프라인 / 다운로드 작업"])
async def get_jobs_by_customer(
    customer_id: UUID,
    conn=Depends(get_db),
    status: DataStatus | None = None,
    limit: int = Query(default=100, le=1000),
):
    conditions = ["customer_id = $1"]
    params: list = [customer_id]

    if status:
        params.append(status.value)
        conditions.append(f"status = ${len(params)}")

    params.append(limit)
    query = f"SELECT * FROM zip_download_jobs WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# 편집
@router.patch("/{job_id}", response_model=ZipDownloadJob, summary="다운로드 작업 상태 수정", tags=["데이터 파이프라인 / 다운로드 작업"])
async def update_zip_download_job(job_id: UUID, body: ZipDownloadJobUpdate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM zip_download_jobs WHERE id = $1", job_id):
        raise HTTPException(status_code=404, detail="해당 다운로드 작업을 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    if "status" in updates:
        updates["status"] = updates["status"].value

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE zip_download_jobs SET {fields} WHERE id = $1 RETURNING *",
        job_id, *list(updates.values()),
    )
    return dict(row)
