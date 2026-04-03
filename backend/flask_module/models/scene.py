from datetime import datetime

from flask_module.db import db


class Device(db.Model):
    """Represents a LED Matrix device"""

    # Communication protocol constants
    PROTOCOL_JSON = "json_api"  # JSON API (for small devices, <256 LEDs)
    PROTOCOL_UDP_DNRGB = "udp_dnrgb"  # UDP DNRGB (unlimited LEDs)

    PROTOCOL_CHOICES = [
        (PROTOCOL_JSON, "JSON API (HTTP) - Up to 256 LEDs"),
        (PROTOCOL_UDP_DNRGB, "UDP DNRGB - Unlimited LEDs (Recommended)"),
    ]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(15), unique=True, nullable=False)  # IPv4 address
    matrix_width = db.Column(db.Integer, default=16)  # e.g., 16 or 32
    matrix_height = db.Column(db.Integer, default=16)  # e.g., 16
    communication_protocol = db.Column(db.String(20), default=PROTOCOL_JSON)  # Protocol to use
    chain_count = db.Column(
        db.Integer, default=1
    )  # Number of parallel chains/segments (e.g., 4 for 4x1024)
    segment_id = db.Column(
        db.Integer, default=0
    )  # WLED Segment ID (0-15, for multi-segment devices)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    scenes = db.relationship("Scene", secondary="scene_device_association", backref="devices")

    def __repr__(self):
        return f"<Device {self.name} ({self.ip_address})>"


class Scene(db.Model):
    """Represents a LED animation scene"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unique_id = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    # Matrix configuration
    matrix_width = db.Column(db.Integer, default=16)
    matrix_height = db.Column(db.Integer, default=16)

    # Timing
    default_frame_duration = db.Column(db.Float, default=5.0)  # seconds between frames

    # Playback mode
    loop_mode = db.Column(db.String(10), default="once")  # "once" or "loop"

    # Owner/Creator
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    frames = db.relationship("Frame", backref="scene", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Scene {self.name} ({self.matrix_width}x{self.matrix_height})>"

    def to_dict(self):
        """Convert scene to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "unique_id": self.unique_id,
            "description": self.description,
            "matrix_width": self.matrix_width,
            "matrix_height": self.matrix_height,
            "default_frame_duration": self.default_frame_duration,
            "loop_mode": self.loop_mode,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "frame_count": len(self.frames),
        }


class Frame(db.Model):
    """Represents a single frame in a scene animation"""

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"), nullable=False)

    # Frame ordering
    frame_index = db.Column(db.Integer, nullable=False)  # 0-based index

    # Pixel data as JSON
    # Format: {"pixels": [{"index": 0, "color": [R, G, B]}, ...]}
    pixel_data = db.Column(db.JSON, nullable=False, default={})

    # Timing for this frame
    duration = db.Column(db.Float)  # If None, uses scene's default_frame_duration

    # Brightness for this frame (0-255)
    brightness = db.Column(db.Integer, default=255)  # Full brightness (100%) by default

    # Color channel intensity multipliers (0-100, default 10 = reduced to 10%)
    # These multiply the respective color channels in the pixels
    # 100 = full intensity, 50 = half intensity, 10 = 10%, 0 = no color
    color_r = db.Column(db.Integer, default=10)  # Red channel intensity (0-100), default 10%
    color_g = db.Column(db.Integer, default=10)  # Green channel intensity (0-100), default 10%
    color_b = db.Column(db.Integer, default=10)  # Blue channel intensity (0-100), default 10%

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("scene_id", "frame_index", name="unique_scene_frame_idx"),
    )

    def __repr__(self):
        return f"<Frame {self.scene_id}:{self.frame_index}>"

    def to_dict(self):
        """Convert frame to dictionary"""
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "frame_index": self.frame_index,
            "pixel_data": self.pixel_data,
            "duration": self.duration,
            "brightness": self.brightness,
            "color_r": self.color_r,
            "color_g": self.color_g,
            "color_b": self.color_b,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# Association table for Scene <-> Device many-to-many relationship
scene_device_association = db.Table(
    "scene_device_association",
    db.Column("scene_id", db.Integer, db.ForeignKey("scene.id"), primary_key=True),
    db.Column("device_id", db.Integer, db.ForeignKey("device.id"), primary_key=True),
    db.Column("created_at", db.DateTime, default=datetime.utcnow),
)
