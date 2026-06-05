from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.pipeline import AudioRecording, DataStatus
from ...database.db import get_db

router = APIRouter(prefix="/audio-recordings")


class AudioRecordingUpdate(BaseModel):
    status: DataStatus | None = None
    file_size_bytes: int | None = None


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[AudioRecording], summary="고객사별 오디오 녹음 조회", tags=["데이터 파이프라인 / 오디오 녹음"])
async def get_recordings_by_customer(
    customer_id: UUID,
    conn=Depends(get_db),
    status: DataStatus | None = None,
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    conditions = ["customer_id = $1"]
    params: list = [customer_id]

    if status:
        params.append(status.value)
        conditions.append(f"status = ${len(params)}")
    if start:
        params.append(start)
        conditions.append(f"captured_at >= ${len(params)}")
    if end:
        params.append(end)
        conditions.append(f"captured_at <= ${len(params)}")

    params.append(limit)
    query = f"SELECT * FROM audio_recordings WHERE {' AND '.join(conditions)} ORDER BY captured_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


@router.get("/by-server/{server_id}", response_model=list[AudioRecording], summary="서버별 오디오 녹음 조회", tags=["데이터 파이프라인 / 오디오 녹음"])
async def get_recordings_by_server(
    server_id: UUID,
    conn=Depends(get_db),
    status: DataStatus | None = None,
    limit: int = Query(default=100, le=1000),
):
    conditions = ["server_id = $1"]
    params: list = [server_id]

    if status:
        params.append(status.value)
        conditions.append(f"status = ${len(params)}")

    params.append(limit)
    query = f"SELECT * FROM audio_recordings WHERE {' AND '.join(conditions)} ORDER BY captured_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# 편집
@router.patch("/{recording_id}", response_model=AudioRecording, summary="오디오 녹음 정보 수정", tags=["데이터 파이프라인 / 오디오 녹음"])
async def update_audio_recording(recording_id: UUID, body: AudioRecordingUpdate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM audio_recordings WHERE id = $1", recording_id):
        raise HTTPException(status_code=404, detail="해당 녹음을 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    if "status" in updates:
        updates["status"] = updates["status"].value

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE audio_recordings SET {fields} WHERE id = $1 RETURNING *",
        recording_id, *list(updates.values()),
    )
    return dict(row)
