"""
SQLAlchemy models and Pydantic schemas for WLED Matrix Manager
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship

from .database import Base

# ─── Association Table ───────────────────────────────────────────

scene_device_association = Table(
    "scene_device_association",
    Base.metadata,
    Column("scene_id", Integer, ForeignKey("scenes.id"), primary_key=True),
    Column("device_id", Integer, ForeignKey("devices.id"), primary_key=True),
)

# ─── SQLAlchemy ORM Models ───────────────────────────────────────


class Device(Base):
    __tablename__ = "devices"

    PROTOCOL_JSON = "json_api"
    PROTOCOL_UDP_DNRGB = "udp_dnrgb"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    ip_address = Column(String(45), unique=True, nullable=False)
    ha_entity_id = Column(String(200), nullable=True)  # Home Assistant entity ID
    matrix_width = Column(Integer, default=16)
    matrix_height = Column(Integer, default=16)
    communication_protocol = Column(String(20), default=PROTOCOL_UDP_DNRGB)
    chain_count = Column(Integer, default=1)
    segment_id = Column(Integer, default=0)
    base_brightness = Column(Integer, default=255)  # Device-level brightness (0-255)
    scale_mode = Column(String(20), default="stretch")  # none, stretch, tile, center
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenes = relationship(
        "Scene", secondary=scene_device_association, back_populates="devices"
    )


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    matrix_width = Column(Integer, default=16)
    matrix_height = Column(Integer, default=16)
    default_frame_duration = Column(Float, default=1.0)
    loop_mode = Column(String(10), default="once")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    frames = relationship(
        "Frame",
        back_populates="scene",
        cascade="all, delete-orphan",
        order_by="Frame.frame_index",
    )
    devices = relationship(
        "Device", secondary=scene_device_association, back_populates="scenes"
    )


class Frame(Base):
    __tablename__ = "frames"

    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    frame_index = Column(Integer, nullable=False)
    pixel_data = Column(JSON, nullable=False, default=dict)
    duration = Column(Float, nullable=True)
    brightness = Column(Integer, default=255)
    color_r = Column(Integer, default=100)
    color_g = Column(Integer, default=100)
    color_b = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scene = relationship("Scene", back_populates="frames")


# ─── Pydantic Schemas (API) ─────────────────────────────────────


class Status(BaseModel):
    status: str
    version: str
    message: str


class HAEntity(BaseModel):
    entity_id: str
    state: str
    attributes: dict = {}


class DeviceCreate(BaseModel):
    name: str
    ip_address: str
    ha_entity_id: Optional[str] = None
    matrix_width: int = 16
    matrix_height: int = 16
    communication_protocol: str = "udp_dnrgb"
    chain_count: int = 1
    segment_id: int = 0
    base_brightness: int = 255
    scale_mode: str = "stretch"


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    ha_entity_id: Optional[str] = None
    matrix_width: Optional[int] = None
    matrix_height: Optional[int] = None
    communication_protocol: Optional[str] = None
    chain_count: Optional[int] = None
    segment_id: Optional[int] = None
    base_brightness: Optional[int] = None
    scale_mode: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    ha_entity_id: Optional[str] = None
    matrix_width: int
    matrix_height: int
    communication_protocol: str
    chain_count: int
    segment_id: int
    base_brightness: int = 255
    scale_mode: str = "stretch"
    is_active: bool
    is_healthy: Optional[bool] = None

    class Config:
        from_attributes = True


class FrameData(BaseModel):
    frame_index: int
    pixel_data: dict
    duration: Optional[float] = None
    brightness: int = 255
    color_r: int = 100
    color_g: int = 100
    color_b: int = 100


class SceneCreate(BaseModel):
    name: str
    description: Optional[str] = None
    matrix_width: int = 16
    matrix_height: int = 16
    default_frame_duration: float = 1.0
    loop_mode: str = "once"
    device_ids: list[int] = []
    frames: list[FrameData] = []


class SceneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    matrix_width: Optional[int] = None
    matrix_height: Optional[int] = None
    default_frame_duration: Optional[float] = None
    loop_mode: Optional[str] = None
    device_ids: Optional[list[int]] = None
    frames: Optional[list[FrameData]] = None


class SceneResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    matrix_width: int
    matrix_height: int
    default_frame_duration: float
    loop_mode: str
    is_active: bool
    frame_count: int
    device_ids: list[int] = []
    frames: list[FrameData] = []

    class Config:
        from_attributes = True


class PlaybackRequest(BaseModel):
    device_ids: list[int] = []


class PlaybackStatus(BaseModel):
    scene_id: int
    is_playing: bool
    loop_mode: str
