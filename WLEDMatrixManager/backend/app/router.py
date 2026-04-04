"""
API Router — scenes, devices, playback, import/export, image upload
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .binary_format import binary_to_scene, scene_to_binary
from .database import get_session
from .device_controller import DeviceController
from .models import (
    Device,
    DeviceCreate,
    DeviceResponse,
    DeviceUpdate,
    Frame,
    FrameData,
    PlaybackRequest,
    Scene,
    SceneCreate,
    SceneResponse,
    SceneUpdate,
    Status,
)
from .scene_playback import (
    get_all_playback_status,
    start_scene_playback,
    stop_scene_playback,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])

# ─── Status ──────────────────────────────────────────────────────


@router.get("/status", response_model=Status)
async def get_status():
    return Status(
        status="running", version="1.2.0", message="WLED Matrix Manager is running"
    )


# ─── Devices ─────────────────────────────────────────────────────


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Device).where(Device.is_active == True))
    devices = result.scalars().all()
    return [DeviceResponse.model_validate(d) for d in devices]


@router.post("/devices", response_model=DeviceResponse)
async def create_device(data: DeviceCreate, db: AsyncSession = Depends(get_session)):
    device = Device(**data.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int, data: DeviceUpdate, db: AsyncSession = Depends(get_session)
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(device, k, v)
    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.delete("/devices/{device_id}")
async def delete_device(device_id: int, db: AsyncSession = Depends(get_session)):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    device.is_active = False
    await db.commit()
    return {"success": True}


@router.get("/devices/{device_id}/health")
async def check_device_health(device_id: int, db: AsyncSession = Depends(get_session)):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    healthy = await DeviceController.check_health(device.ip_address)
    return {"device_id": device_id, "healthy": healthy}


# ─── HA Discovery ────────────────────────────────────────────────


@router.get("/ha/discover")
async def discover_ha_devices():
    """Discover WLED devices from Home Assistant."""
    from app.ha_client import HAClient

    client = HAClient()
    await client.connect()
    try:
        devices = await client.discover_wled_devices()
        return {"devices": devices}
    finally:
        await client.disconnect()


# ─── Scenes ──────────────────────────────────────────────────────


@router.get("/scenes", response_model=List[SceneResponse])
async def list_scenes(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Scene)
        .where(Scene.is_active == True)
        .options(selectinload(Scene.frames), selectinload(Scene.devices))
    )
    scenes = result.scalars().all()
    out = []
    for s in scenes:
        out.append(
            SceneResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                matrix_width=s.matrix_width,
                matrix_height=s.matrix_height,
                default_frame_duration=s.default_frame_duration,
                loop_mode=s.loop_mode,
                is_active=s.is_active,
                frame_count=len(s.frames),
                device_ids=[d.id for d in s.devices],
                frames=[
                    FrameData(
                        frame_index=f.frame_index,
                        pixel_data=f.pixel_data or {},
                        duration=f.duration,
                        brightness=f.brightness or 255,
                        color_r=f.color_r or 100,
                        color_g=f.color_g or 100,
                        color_b=f.color_b or 100,
                    )
                    for f in sorted(s.frames, key=lambda x: x.frame_index)
                ],
            )
        )
    return out


@router.get("/scenes/{scene_id}", response_model=SceneResponse)
async def get_scene(scene_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Scene)
        .where(Scene.id == scene_id)
        .options(selectinload(Scene.frames), selectinload(Scene.devices))
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Scene not found")
    return SceneResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        matrix_width=s.matrix_width,
        matrix_height=s.matrix_height,
        default_frame_duration=s.default_frame_duration,
        loop_mode=s.loop_mode,
        is_active=s.is_active,
        frame_count=len(s.frames),
        device_ids=[d.id for d in s.devices],
        frames=[
            FrameData(
                frame_index=f.frame_index,
                pixel_data=f.pixel_data or {},
                duration=f.duration,
                brightness=f.brightness or 255,
                color_r=f.color_r or 100,
                color_g=f.color_g or 100,
                color_b=f.color_b or 100,
            )
            for f in sorted(s.frames, key=lambda x: x.frame_index)
        ],
    )


@router.post("/scenes", response_model=SceneResponse)
async def create_scene(data: SceneCreate, db: AsyncSession = Depends(get_session)):
    scene = Scene(
        name=data.name,
        description=data.description,
        matrix_width=data.matrix_width,
        matrix_height=data.matrix_height,
        default_frame_duration=data.default_frame_duration,
        loop_mode=data.loop_mode,
    )
    db.add(scene)
    await db.flush()

    # Add frames
    for fd in data.frames:
        frame = Frame(
            scene_id=scene.id,
            frame_index=fd.frame_index,
            pixel_data=fd.pixel_data,
            duration=fd.duration,
            brightness=fd.brightness,
            color_r=fd.color_r,
            color_g=fd.color_g,
            color_b=fd.color_b,
        )
        db.add(frame)

    # Link devices
    if data.device_ids:
        result = await db.execute(select(Device).where(Device.id.in_(data.device_ids)))
        devices = result.scalars().all()
        scene.devices = list(devices)

    await db.commit()
    await db.refresh(scene, ["frames", "devices"])

    return SceneResponse(
        id=scene.id,
        name=scene.name,
        description=scene.description,
        matrix_width=scene.matrix_width,
        matrix_height=scene.matrix_height,
        default_frame_duration=scene.default_frame_duration,
        loop_mode=scene.loop_mode,
        is_active=scene.is_active,
        frame_count=len(scene.frames),
        device_ids=[d.id for d in scene.devices],
        frames=[
            FrameData(
                frame_index=f.frame_index,
                pixel_data=f.pixel_data or {},
                duration=f.duration,
                brightness=f.brightness or 255,
                color_r=f.color_r or 100,
                color_g=f.color_g or 100,
                color_b=f.color_b or 100,
            )
            for f in sorted(scene.frames, key=lambda x: x.frame_index)
        ],
    )


@router.put("/scenes/{scene_id}", response_model=SceneResponse)
async def update_scene(
    scene_id: int, data: SceneUpdate, db: AsyncSession = Depends(get_session)
):
    result = await db.execute(
        select(Scene)
        .where(Scene.id == scene_id)
        .options(selectinload(Scene.frames), selectinload(Scene.devices))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(404, "Scene not found")

    # Update scalar fields
    for field in [
        "name",
        "description",
        "matrix_width",
        "matrix_height",
        "default_frame_duration",
        "loop_mode",
    ]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(scene, field, val)

    # Replace frames if provided
    if data.frames is not None:
        for old_frame in scene.frames:
            await db.delete(old_frame)
        await db.flush()
        for fd in data.frames:
            frame = Frame(
                scene_id=scene.id,
                frame_index=fd.frame_index,
                pixel_data=fd.pixel_data,
                duration=fd.duration,
                brightness=fd.brightness,
                color_r=fd.color_r,
                color_g=fd.color_g,
                color_b=fd.color_b,
            )
            db.add(frame)

    # Update device links
    if data.device_ids is not None:
        result2 = await db.execute(select(Device).where(Device.id.in_(data.device_ids)))
        scene.devices = list(result2.scalars().all())

    await db.commit()
    await db.refresh(scene, ["frames", "devices"])

    return SceneResponse(
        id=scene.id,
        name=scene.name,
        description=scene.description,
        matrix_width=scene.matrix_width,
        matrix_height=scene.matrix_height,
        default_frame_duration=scene.default_frame_duration,
        loop_mode=scene.loop_mode,
        is_active=scene.is_active,
        frame_count=len(scene.frames),
        device_ids=[d.id for d in scene.devices],
        frames=[
            FrameData(
                frame_index=f.frame_index,
                pixel_data=f.pixel_data or {},
                duration=f.duration,
                brightness=f.brightness or 255,
                color_r=f.color_r or 100,
                color_g=f.color_g or 100,
                color_b=f.color_b or 100,
            )
            for f in sorted(scene.frames, key=lambda x: x.frame_index)
        ],
    )


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: int, db: AsyncSession = Depends(get_session)):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    scene.is_active = False
    await db.commit()
    return {"success": True}


# ─── Playback ────────────────────────────────────────────────────


@router.post("/scenes/{scene_id}/play")
async def play_scene(
    scene_id: int, req: PlaybackRequest, db: AsyncSession = Depends(get_session)
):
    result = await db.execute(
        select(Scene)
        .where(Scene.id == scene_id)
        .options(selectinload(Scene.frames), selectinload(Scene.devices))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(404, "Scene not found")

    # Determine target devices
    device_ids = req.device_ids or [d.id for d in scene.devices]
    if not device_ids:
        raise HTTPException(400, "No devices specified")

    result2 = await db.execute(select(Device).where(Device.id.in_(device_ids)))
    devices = result2.scalars().all()

    devices_info = [
        {
            "ip_address": d.ip_address,
            "communication_protocol": d.communication_protocol,
            "matrix_width": d.matrix_width,
            "matrix_height": d.matrix_height,
            "chain_count": d.chain_count,
            "segment_id": d.segment_id,
        }
        for d in devices
    ]

    frames_data = [
        {
            "frame_index": f.frame_index,
            "pixel_data": f.pixel_data or {},
            "duration": f.duration or scene.default_frame_duration,
            "brightness": f.brightness or 255,
            "color_r": f.color_r or 100,
            "color_g": f.color_g or 100,
            "color_b": f.color_b or 100,
        }
        for f in sorted(scene.frames, key=lambda x: x.frame_index)
    ]

    start_scene_playback(scene.id, devices_info, frames_data, scene.loop_mode)
    return {"success": True, "scene_id": scene.id}


@router.post("/scenes/{scene_id}/stop")
async def stop_scene(scene_id: int):
    stop_scene_playback(scene_id)
    return {"success": True}


@router.get("/playback/status")
async def playback_status():
    return get_all_playback_status()


# ─── Export / Import ─────────────────────────────────────────────


@router.get("/scenes/{scene_id}/export")
async def export_scene(scene_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Scene).where(Scene.id == scene_id).options(selectinload(Scene.frames))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(404, "Scene not found")

    scene_dict = {
        "name": scene.name,
        "description": scene.description,
        "matrix_width": scene.matrix_width,
        "matrix_height": scene.matrix_height,
        "loop_mode": scene.loop_mode,
        "frames": [
            {
                "frame_index": f.frame_index,
                "pixel_data": f.pixel_data or {},
                "duration": f.duration or scene.default_frame_duration,
                "brightness": f.brightness or 255,
                "color_r": f.color_r or 100,
                "color_g": f.color_g or 100,
                "color_b": f.color_b or 100,
            }
            for f in sorted(scene.frames, key=lambda x: x.frame_index)
        ],
    }
    binary_data = scene_to_binary(scene_dict)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in scene.name)
    return Response(
        content=binary_data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.ledm"},
    )


@router.post("/scenes/import")
async def import_scene(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_session)
):
    content = await file.read()
    try:
        scene_dict = binary_to_scene(content)
    except ValueError as e:
        raise HTTPException(400, str(e))

    scene = Scene(
        name=scene_dict["name"],
        description=scene_dict.get("description"),
        matrix_width=scene_dict["matrix_width"],
        matrix_height=scene_dict["matrix_height"],
        loop_mode=scene_dict.get("loop_mode", "once"),
    )
    db.add(scene)
    await db.flush()

    for fd in scene_dict.get("frames", []):
        frame = Frame(
            scene_id=scene.id,
            frame_index=fd["frame_index"],
            pixel_data=fd.get("pixel_data", {}),
            duration=fd.get("duration"),
            brightness=fd.get("brightness", 255),
            color_r=fd.get("color_r", 100),
            color_g=fd.get("color_g", 100),
            color_b=fd.get("color_b", 100),
        )
        db.add(frame)

    await db.commit()
    await db.refresh(scene, ["frames"])
    return {"success": True, "scene_id": scene.id, "name": scene.name}


# ─── Image Upload ────────────────────────────────────────────────


@router.post("/image/convert")
async def convert_image(
    file: UploadFile = File(...),
    width: int = Query(16, ge=1, le=256),
    height: int = Query(16, ge=1, le=256),
    colors: int = Query(256, ge=2, le=256),
):
    """Convert an uploaded image to pixel data."""
    from .image_converter import ImageToPixelConverter

    content = await file.read()
    try:
        pixel_data = ImageToPixelConverter.convert_bytes(content, width, height, colors)
        return pixel_data
    except Exception as e:
        raise HTTPException(400, f"Image conversion failed: {e}")


# ─── Stats ───────────────────────────────────────────────────────


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_session)):
    scenes_result = await db.execute(select(Scene).where(Scene.is_active == True))
    devices_result = await db.execute(select(Device).where(Device.is_active == True))
    scenes = scenes_result.scalars().all()
    devices = devices_result.scalars().all()
    playbacks = get_all_playback_status()

    return {
        "total_scenes": len(scenes),
        "total_devices": len(devices),
        "active_playbacks": sum(1 for p in playbacks.values() if p.get("is_playing")),
    }
