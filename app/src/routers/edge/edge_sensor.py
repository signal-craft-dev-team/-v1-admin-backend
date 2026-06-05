from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from signalcraft_models.edge import EdgeSensor, SensorFace, SensorHorizontalPosition, SensorVerticalPosition
from ...database.db import get_db

router = APIRouter(prefix="/edge-sensors")


class EdgeSensorCreate(BaseModel):
    server_id: UUID
    machine_id: UUID
    label: str
    hardware_id: str
    sensor_face: SensorFace | None = None
    horizontal_position: SensorHorizontalPosition | None = None
    vertical_position: SensorVerticalPosition | None = None
    position_description: str | None = None
    installation_image: str | None = None


class EdgeSensorUpdate(BaseModel):
    server_id: UUID | None = None
    machine_id: UUID | None = None
    label: str | None = None
    hardware_id: str | None = None
    sensor_face: SensorFace | None = None
    horizontal_position: SensorHorizontalPosition | None = None
    vertical_position: SensorVerticalPosition | None = None
    position_description: str | None = None
    installation_image: str | None = None


# 조회
@router.get("/by-server/{server_id}", response_model=list[EdgeSensor], summary="서버별 센서 목록 조회", tags=["엣지 센서 / 조회"])
async def get_sensors_by_server(server_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM edge_sensor WHERE server_id = $1 ORDER BY created_at",
        server_id,
    )
    return [dict(row) for row in rows]


@router.get("/by-machine/{machine_id}", response_model=list[EdgeSensor], summary="설비별 센서 목록 조회", tags=["엣지 센서 / 조회"])
async def get_sensors_by_machine(machine_id: UUID, conn=Depends(get_db)):
    rows = await conn.fetch(
        "SELECT * FROM edge_sensor WHERE machine_id = $1 ORDER BY created_at",
        machine_id,
    )
    return [dict(row) for row in rows]


# 생성
@router.post("", response_model=EdgeSensor, status_code=201, summary="엣지 센서 등록", tags=["엣지 센서 / 생성"])
async def create_edge_sensor(body: EdgeSensorCreate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", body.server_id):
        raise HTTPException(status_code=404, detail=f"server_id {body.server_id} 를 찾을 수 없습니다.")
    if not await conn.fetchval("SELECT id FROM machine WHERE id = $1", body.machine_id):
        raise HTTPException(status_code=404, detail=f"machine_id {body.machine_id} 를 찾을 수 없습니다.")

    if await conn.fetchval("SELECT id FROM edge_sensor WHERE hardware_id = $1", body.hardware_id):
        raise HTTPException(status_code=409, detail=f"hardware_id '{body.hardware_id}' 는 이미 등록된 센서입니다.")

    row = await conn.fetchrow(
        """
        INSERT INTO edge_sensor (
            id, server_id, machine_id, label, hardware_id,
            sensor_face, horizontal_position, vertical_position,
            position_description, installation_image
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        RETURNING *
        """,
        uuid4(), body.server_id, body.machine_id, body.label, body.hardware_id,
        body.sensor_face.value if body.sensor_face else None,
        body.horizontal_position.value if body.horizontal_position else None,
        body.vertical_position.value if body.vertical_position else None,
        body.position_description, body.installation_image,
    )
    return dict(row)


# 수정
@router.patch("/{sensor_id}", response_model=EdgeSensor, summary="엣지 센서 정보 수정", tags=["엣지 센서 / 수정"])
async def update_edge_sensor(sensor_id: UUID, body: EdgeSensorUpdate, conn=Depends(get_db)):
    if not await conn.fetchval("SELECT id FROM edge_sensor WHERE id = $1", sensor_id):
        raise HTTPException(status_code=404, detail="해당 엣지 센서를 찾을 수 없습니다.")

    if body.server_id and not await conn.fetchval("SELECT id FROM edge_server WHERE id = $1", body.server_id):
        raise HTTPException(status_code=404, detail=f"server_id {body.server_id} 를 찾을 수 없습니다.")
    if body.machine_id and not await conn.fetchval("SELECT id FROM machine WHERE id = $1", body.machine_id):
        raise HTTPException(status_code=404, detail=f"machine_id {body.machine_id} 를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다.")

    # enum → value 변환
    for key in ("sensor_face", "horizontal_position", "vertical_position"):
        if key in updates and updates[key] is not None:
            updates[key] = updates[key].value

    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
    row = await conn.fetchrow(
        f"UPDATE edge_sensor SET {fields}, updated_at = now() WHERE id = $1 RETURNING *",
        sensor_id, *list(updates.values()),
    )
    return dict(row)


# 삭제 (Hard only — is_active 없음)
@router.delete("/hard/{sensor_id}", summary="엣지 센서 완전 삭제 (Hard Delete)", tags=["엣지 센서 / 삭제"])
async def hard_delete_edge_sensor(sensor_id: UUID, conn=Depends(get_db)):
    result = await conn.execute("DELETE FROM edge_sensor WHERE id = $1", sensor_id)
    if int(result.split()[-1]) == 0:
        raise HTTPException(status_code=404, detail="해당 엣지 센서를 찾을 수 없습니다.")
    return {"deleted": True, "id": str(sensor_id)}
