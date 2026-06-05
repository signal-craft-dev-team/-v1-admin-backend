from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.pipeline import AudioSlice
from ...database.db import get_db

router = APIRouter(prefix="/audio-slices")


class AudioSliceUpdate(BaseModel):
    start_offset_ms: int | None = None
    duration_ms: int | None = None


# 조회
@router.get("/by-recording/{recording_id}", response_model=list[AudioSlice], summary="녹음별 오디오 슬라이스 조회", tags=["데이터 파이프라인 / 오디오 슬라이스"])
async def get_slices_by_recording(
    recording_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
):
    rows = await conn.fetch(
        "SELECT * FROM audio_slices WHERE recording_id = $1 ORDER BY start_offset_ms LIMIT $2",
        recording_id, limit,
    )
    return [dict(row) for row in rows]


@router.get("/by-sensor/{sensor_id}", response_model=list[AudioSlice], summary="센서별 오디오 슬라이스 조회", tags=["데이터 파이프라인 / 오디오 슬라이스"])
async def get_slices_by_sensor(
    sensor_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
):
    rows = await conn.fetch(
        "SELECT * FROM audio_slices WHERE sensor_id = $1 ORDER BY sliced_at DESC LIMIT $2",
        sensor_id, limit,
    )
    return [dict(row) for row in rows]


# 편집
@router.patch("/{slice_id}", response_model=AudioSlice, summary="오디오 슬라이스 수정", tags=["데이터 파이프라인 / 오디오 슬라이스"])
async def update_audio_slice(slice_id: UUID, body: AudioSliceUpdate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM audio_slices WHERE id = $1", slice_id):
        raise HTTPException(status_code=404, detail="해당 슬라이스를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE audio_slices SET {fields} WHERE id = $1 RETURNING *",
        slice_id, *list(updates.values()),
    )
    return dict(row)
