from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from signalcraft_models.ml import InferenceResult
from ...database.db import get_db

router = APIRouter(prefix="/inference-results")


class InferenceResultCreate(BaseModel):
    audio_captured_at: datetime
    inferred_at: datetime
    # TODO: ML 팀 협의 후 NOT NULL 예정
    customer_id: UUID | None = None
    server_id: UUID | None = None
    sensor_id: UUID | None = None
    audio_slice_id: UUID | None = None


# 조회
@router.get("/by-customer/{customer_id}", response_model=list[InferenceResult], summary="고객사별 추론 결과 조회", tags=["ML 결과 / 추론 결과"])
async def get_results_by_customer(
    customer_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            "SELECT * FROM inference_results WHERE customer_id = $1 AND inferred_at BETWEEN $2 AND $3 ORDER BY inferred_at DESC LIMIT $4",
            customer_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM inference_results WHERE customer_id = $1 ORDER BY inferred_at DESC LIMIT $2",
            customer_id, limit,
        )
    return [dict(row) for row in rows]


@router.get("/by-sensor/{sensor_id}", response_model=list[InferenceResult], summary="센서별 추론 결과 조회", tags=["ML 결과 / 추론 결과"])
async def get_results_by_sensor(
    sensor_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start and end:
        rows = await conn.fetch(
            "SELECT * FROM inference_results WHERE sensor_id = $1 AND inferred_at BETWEEN $2 AND $3 ORDER BY inferred_at DESC LIMIT $4",
            sensor_id, start, end, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM inference_results WHERE sensor_id = $1 ORDER BY inferred_at DESC LIMIT $2",
            sensor_id, limit,
        )
    return [dict(row) for row in rows]


@router.get("/by-server/{server_id}", response_model=list[InferenceResult], summary="서버별 추론 결과 조회", tags=["ML 결과 / 추론 결과"])
async def get_results_by_server(
    server_id: UUID,
    conn=Depends(get_db),
    limit: int = Query(default=100, le=1000),
):
    rows = await conn.fetch(
        "SELECT * FROM inference_results WHERE server_id = $1 ORDER BY inferred_at DESC LIMIT $2",
        server_id, limit,
    )
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=InferenceResult, status_code=201, summary="추론 결과 기록", tags=["ML 결과 / 추론 결과"])
async def create_inference_result(body: InferenceResultCreate, conn=Depends(get_db)):
    if body.customer_id and not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if body.server_id and not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", body.server_id):
        raise HTTPException(status_code=404, detail=f"server_id {body.server_id} 를 찾을 수 없습니다.")
    if body.sensor_id and not await conn.fetchval("SELECT id FROM edge_sensor WHERE id = $1", body.sensor_id):
        raise HTTPException(status_code=404, detail=f"sensor_id {body.sensor_id} 를 찾을 수 없습니다.")
    if body.audio_slice_id and not await conn.fetchval("SELECT id FROM audio_slices WHERE id = $1", body.audio_slice_id):
        raise HTTPException(status_code=404, detail=f"audio_slice_id {body.audio_slice_id} 를 찾을 수 없습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO inference_results (
            id, customer_id, server_id, sensor_id, audio_slice_id,
            audio_captured_at, inferred_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        uuid4(), body.customer_id, body.server_id, body.sensor_id,
        body.audio_slice_id, body.audio_captured_at, body.inferred_at,
    )
    return dict(row)
