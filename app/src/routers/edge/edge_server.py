from uuid import UUID, uuid4
from datetime import datetime, time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.edge import EdgeServer
from ...database.db import get_db

router = APIRouter(prefix="/edge-servers")


def _row(row) -> dict:
    d = dict(row)
    for key in ("tailscale_ip_address", "mac_address"):
        if d.get(key) is not None:
            d[key] = str(d[key])
    return d


class EdgeServerCreate(BaseModel):
    customer_id: UUID
    place_id: UUID
    hostname: str
    tailscale_host_address: str | None = None
    tailscale_ip_address: str | None = None
    mac_address: str | None = None
    hardware_model: str | None = None
    capture_duration_ms: int | None = None
    upload_interval_ms: int | None = None
    active_hours_start: time | None = None
    active_hours_end: time | None = None
    sensor_captured_gap_ms: int | None = None
    installed_at: datetime | None = None


class EdgeServerUpdate(BaseModel):
    customer_id: UUID | None = None
    place_id: UUID | None = None
    hostname: str | None = None
    tailscale_host_address: str | None = None
    tailscale_ip_address: str | None = None
    mac_address: str | None = None
    hardware_model: str | None = None
    capture_duration_ms: int | None = None
    upload_interval_ms: int | None = None
    active_hours_start: time | None = None
    active_hours_end: time | None = None
    sensor_captured_gap_ms: int | None = None
    installed_at: datetime | None = None


# 조회 — customer → edge_server → edge_sensor cascade
@router.get("/by-customer/{customer_id}", summary="고객사별 엣지 서버 및 센서 cascade 조회", tags=["엣지 서버 / 조회"])
async def get_servers_by_customer(customer_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        r"""
        SELECT
            es.*,
            COALESCE(
                json_agg(
                    json_build_object(
                        'id',                   esn.id,
                        'server_id',            esn.server_id,
                        'machine_id',           esn.machine_id,
                        'label',                esn.label,
                        'hardware_id',          esn.hardware_id,
                        'sensor_face',          esn.sensor_face,
                        'horizontal_position',  esn.horizontal_position,
                        'vertical_position',    esn.vertical_position,
                        'position_description', esn.position_description,
                        'installation_image',   esn.installation_image,
                        'created_at',           esn.created_at,
                        'updated_at',           esn.updated_at
                    ) ORDER BY esn.created_at
                ) FILTER (WHERE esn.id IS NOT NULL),
                '[]'
            ) AS sensors
        FROM edge_server es
        LEFT JOIN edge_sensor esn ON esn.server_id = es.id
        WHERE es.customer_id = $1
        GROUP BY es.id
        ORDER BY es.created_at DESC
        """,
        customer_id,
    )
    return [_row(row) for row in rows]


@router.get("/by-place/{place_id}", response_model=list[EdgeServer], summary="현장별 엣지 서버 조회", tags=["엣지 서버 / 조회"])
async def get_servers_by_place(place_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM edge_server WHERE place_id = $1 ORDER BY created_at DESC",
        place_id,
    )
    return [_row(row) for row in rows]


# 생성
@router.post("", response_model=EdgeServer, status_code=201, summary="엣지 서버 등록", tags=["엣지 서버 / 생성"])
async def create_edge_server(body: EdgeServerCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if not await conn.fetchval("SELECT id FROM place WHERE id = $1", body.place_id):
        raise HTTPException(status_code=404, detail=f"place_id {body.place_id} 를 찾을 수 없습니다.")

    duplicate = await conn.fetchval(
        "SELECT id FROM edge_server WHERE customer_id = $1 AND hostname = $2",
        body.customer_id, body.hostname,
    )
    if duplicate:
        raise HTTPException(status_code=409, detail=f"hostname '{body.hostname}' 은 이미 해당 고객사에 등록되어 있습니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO edge_server (
            id, customer_id, place_id, hostname, tailscale_host_address,
            tailscale_ip_address, mac_address, hardware_model,
            capture_duration_ms, upload_interval_ms,
            active_hours_start, active_hours_end,
            sensor_captured_gap_ms, installed_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        RETURNING *
        """,
        uuid4(), body.customer_id, body.place_id, body.hostname,
        body.tailscale_host_address, body.tailscale_ip_address,
        body.mac_address, body.hardware_model,
        body.capture_duration_ms, body.upload_interval_ms,
        body.active_hours_start, body.active_hours_end,
        body.sensor_captured_gap_ms, body.installed_at,
    )
    return _row(row)


# 수정
@router.patch("/{server_id}", response_model=EdgeServer, summary="엣지 서버 정보 수정", tags=["엣지 서버 / 수정"])
async def update_edge_server(server_id: UUID, body: EdgeServerUpdate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", server_id):
        raise HTTPException(status_code=404, detail="해당 엣지 서버를 찾을 수 없습니다.")

    if body.customer_id and not await conn.fetchval("SELECT id FROM customer WHERE id = $1", body.customer_id):
        raise HTTPException(status_code=404, detail=f"customer_id {body.customer_id} 를 찾을 수 없습니다.")
    if body.place_id and not await conn.fetchval("SELECT id FROM place WHERE id = $1", body.place_id):
        raise HTTPException(status_code=404, detail=f"place_id {body.place_id} 를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE edge_server SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        server_id, *list(updates.values()),
    )
    return _row(row)


# 삭제
@router.delete("/hard/{server_id}", summary="엣지 서버 완전 삭제 — 하위 센서 cascade (Hard Delete)", tags=["엣지 서버 / 삭제"])
async def hard_delete_edge_server(server_id: UUID, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", server_id):
        raise HTTPException(status_code=404, detail="해당 엣지 서버를 찾을 수 없습니다.")

    async with conn.transaction():
        await conn.execute("DELETE FROM edge_sensor WHERE server_id = $1", server_id)
        await conn.execute("DELETE FROM edge_server WHERE id = $1", server_id)

    return {"deleted": True, "id": str(server_id)}


@router.delete("/soft/{server_id}", response_model=EdgeServer, summary="엣지 서버 비활성화 (Soft Delete)", tags=["엣지 서버 / 삭제"])
async def soft_delete_edge_server(server_id: UUID, conn=Depends(get_db)):
    row = await conn.fetchrow(
        "UPDATE edge_server SET is_active = false, updated_at = now() WHERE id = $1 RETURNING *",
        server_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="해당 엣지 서버를 찾을 수 없습니다.")
    return _row(row)
