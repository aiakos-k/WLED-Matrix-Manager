from marshmallow import Schema, fields


class DeviceSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    ip_address = fields.Str(required=True)
    matrix_width = fields.Int(load_default=16, dump_default=16)
    matrix_height = fields.Int(load_default=16, dump_default=16)
    communication_protocol = fields.Str(
        load_default="json_api",
        dump_default="json_api",
        validate=lambda x: x in ["json_api", "udp_dnrgb"],
    )
    chain_count = fields.Int(
        load_default=1, dump_default=1
    )  # Number of parallel chains (e.g., 4 for 4x1024)
    segment_id = fields.Int(
        load_default=0, dump_default=0
    )  # WLED Segment ID (0-15, for multi-segment devices)
    is_active = fields.Bool(load_default=True, dump_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class FrameSchema(Schema):
    id = fields.Int(dump_only=True)
    scene_id = fields.Int(required=True)
    frame_index = fields.Int(required=True)
    pixel_data = fields.Dict(load_default={}, dump_default={})
    duration = fields.Float(allow_none=True)
    brightness = fields.Int(load_default=128, dump_default=128)  # 0-255, 50% by default
    color_r = fields.Int(load_default=10, dump_default=10)  # Red intensity 0-100, default 10%
    color_g = fields.Int(load_default=10, dump_default=10)  # Green intensity 0-100, default 10%
    color_b = fields.Int(load_default=10, dump_default=10)  # Blue intensity 0-100, default 10%
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class SceneSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    unique_id = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    matrix_width = fields.Int(load_default=16, dump_default=16)
    matrix_height = fields.Int(load_default=16, dump_default=16)
    default_frame_duration = fields.Float(load_default=5.0, dump_default=5.0)
    loop_mode = fields.Str(load_default="once", dump_default="once")  # "once" or "loop"
    created_by = fields.Int(required=True)
    is_active = fields.Bool(load_default=True, dump_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    frame_count = fields.Int(dump_only=True)
    # Nested relationships
    frames = fields.Nested(FrameSchema, many=True, dump_only=True)
    devices = fields.Nested(DeviceSchema, many=True, dump_only=True)


class SceneDetailSchema(SceneSchema):
    """Detailed scene schema with all related data"""

    pass


class SceneCreateSchema(Schema):
    """Schema for creating a new scene"""

    name = fields.Str(required=True)
    unique_id = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    matrix_width = fields.Int(load_default=16, dump_default=16)
    matrix_height = fields.Int(load_default=16, dump_default=16)
    default_frame_duration = fields.Float(load_default=5.0, dump_default=5.0)
    loop_mode = fields.Str(load_default="once", dump_default="once")  # "once" or "loop"
    device_ids = fields.List(fields.Int(), load_default=[], dump_default=[])


class SceneUpdateSchema(Schema):
    """Schema for updating an existing scene"""

    name = fields.Str()
    description = fields.Str(allow_none=True)
    default_frame_duration = fields.Float()
    loop_mode = fields.Str()  # "once" or "loop"
    is_active = fields.Bool()
    device_ids = fields.List(fields.Int(), allow_none=True)


class FrameCreateSchema(Schema):
    """Schema for creating a frame"""

    frame_index = fields.Int(required=True)
    pixel_data = fields.Dict(required=True)
    duration = fields.Float(allow_none=True)
    brightness = fields.Int(load_default=128, dump_default=128)  # 0-255, 50% by default
    color_r = fields.Int(load_default=10, dump_default=10)  # Red intensity 0-100, default 10%
    color_g = fields.Int(load_default=10, dump_default=10)  # Green intensity 0-100, default 10%
    color_b = fields.Int(load_default=10, dump_default=10)  # Blue intensity 0-100, default 10%


class FrameUpdateSchema(Schema):
    """Schema for updating a frame"""

    frame_index = fields.Int()  # Optional for identifying frame in PATCH operations
    pixel_data = fields.Dict()
    duration = fields.Float()
    brightness = fields.Int()
    color_r = fields.Int()  # Red intensity 0-100
    color_g = fields.Int()  # Green intensity 0-100
    color_b = fields.Int()  # Blue intensity 0-100
    duration = fields.Float(allow_none=True)
    brightness = fields.Int()  # 0-255
