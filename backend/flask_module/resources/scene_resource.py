"""
Scene API Resource - CRUD operations for LED animation scenes
"""

import logging
import os

from flask import current_app, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from werkzeug.utils import secure_filename

from flask_module.db import db, get_or_404
from flask_module.models import Device, Frame, Scene, User
from flask_module.schemas import (
    FrameCreateSchema,
    FrameSchema,
    FrameUpdateSchema,
    SceneCreateSchema,
    SceneSchema,
    SceneUpdateSchema,
)
from flask_module.services.auth_decorators import require_auth
from flask_module.services.device_controller import DeviceController
from flask_module.services.image_to_pixel_converter import ImageToPixelConverter
from flask_module.services.scene_playback import start_scene_playback, stop_scene_playback

logger = logging.getLogger(__name__)

blp = Blueprint("scenes", __name__, url_prefix="/api/scenes", description="Scene management")

scene_schema = SceneSchema()
scenes_schema = SceneSchema(many=True)
scene_create_schema = SceneCreateSchema()
scene_update_schema = SceneUpdateSchema()
frame_schema = FrameSchema()
frames_schema = FrameSchema(many=True)
frame_create_schema = FrameCreateSchema()
frame_update_schema = FrameUpdateSchema()


@blp.route("/")
class SceneList(MethodView):
    @blp.response(200, scenes_schema)
    def get(self):
        """List all active scenes"""
        scenes = Scene.query.filter_by(is_active=True).all()
        return scenes

    @require_auth
    @blp.arguments(scene_create_schema)
    @blp.response(201, scene_schema)
    def post(self, scene_data):
        """Create a new scene (requires authentication)"""
        user_id = request.headers.get("X-User-Id", 1)

        # Check if scene with unique_id already exists
        existing = Scene.query.filter_by(unique_id=scene_data["unique_id"]).first()
        if existing:
            abort(400, message=f"Scene with unique_id '{scene_data['unique_id']}' already exists")

        scene = Scene(
            name=scene_data["name"],
            unique_id=scene_data["unique_id"],
            description=scene_data.get("description"),
            matrix_width=scene_data.get("matrix_width", 16),
            matrix_height=scene_data.get("matrix_height", 16),
            default_frame_duration=scene_data.get("default_frame_duration", 5.0),
            loop_mode=scene_data.get("loop_mode", "once"),
            created_by=user_id,
        )

        # Add devices if provided
        device_ids = scene_data.get("device_ids", [])
        for device_id in device_ids:
            device = get_or_404(Device, device_id)
            scene.devices.append(device)

        db.session.add(scene)
        db.session.flush()  # Flush to get the scene ID

        # Create default first frame (empty/black)
        width = scene_data.get("matrix_width", 16)
        height = scene_data.get("matrix_height", 16)
        default_frame = Frame(
            scene_id=scene.id,
            frame_index=0,
            pixel_data={
                "pixels": [],
                "width": width,
                "height": height,
            },
            duration=scene_data.get("default_frame_duration", 5.0),
        )
        db.session.add(default_frame)
        db.session.commit()
        return scene


@blp.route("/<int:scene_id>")
class SceneDetail(MethodView):
    @blp.response(200, scene_schema)
    def get(self, scene_id):
        """Get scene details with all frames"""
        scene = get_or_404(Scene, scene_id)
        return scene

    @require_auth
    @blp.arguments(scene_update_schema)
    @blp.response(200, scene_schema)
    def patch(self, scene_data, scene_id):
        """Update scene (owner or admin only)"""
        scene = get_or_404(Scene, scene_id)
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        # Update fields
        if "name" in scene_data:
            scene.name = scene_data["name"]
        if "description" in scene_data:
            scene.description = scene_data["description"]
        if "default_frame_duration" in scene_data:
            scene.default_frame_duration = scene_data["default_frame_duration"]
        if "loop_mode" in scene_data:
            scene.loop_mode = scene_data["loop_mode"]
        if "is_active" in scene_data:
            scene.is_active = scene_data["is_active"]

        # Update devices if provided
        if "device_ids" in scene_data and scene_data["device_ids"] is not None:
            scene.devices.clear()
            for device_id in scene_data["device_ids"]:
                device = get_or_404(Device, device_id)
                scene.devices.append(device)

        db.session.commit()
        return scene

    @require_auth
    @blp.response(204)
    def delete(self, scene_id):
        """Delete scene (owner or admin only)"""
        scene = get_or_404(Scene, scene_id)
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to delete this scene")

        db.session.delete(scene)
        db.session.commit()


@blp.route("/<int:scene_id>/frames")
class FrameList(MethodView):
    @blp.response(200, frames_schema)
    def get(self, scene_id):
        """Get all frames for a scene"""
        get_or_404(Scene, scene_id)  # Verify scene exists
        frames = Frame.query.filter_by(scene_id=scene_id).order_by(Frame.frame_index).all()
        return frames

    @require_auth
    @blp.arguments(frame_create_schema)
    @blp.response(201, frame_schema)
    def post(self, frame_data, scene_id):
        """Create a new frame in a scene (owner or admin only)"""
        scene = get_or_404(Scene, scene_id)
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        # Check if frame_index already exists for this scene
        existing = Frame.query.filter_by(
            scene_id=scene_id, frame_index=frame_data["frame_index"]
        ).first()
        if existing:
            abort(
                400,
                message=f"Frame with index {frame_data['frame_index']} already exists in this scene",
            )

        frame = Frame(
            scene_id=scene_id,
            frame_index=frame_data["frame_index"],
            pixel_data=frame_data.get("pixel_data", {}),
            duration=frame_data.get("duration"),
            brightness=frame_data.get("brightness", 255),
            color_r=frame_data.get("color_r", 100),
            color_g=frame_data.get("color_g", 100),
            color_b=frame_data.get("color_b", 100),
        )

        db.session.add(frame)
        db.session.commit()
        return frame

    @require_auth
    @blp.arguments(frame_update_schema)
    @blp.response(200, frame_schema)
    def patch(self, frame_data, scene_id):
        """Update frame by scene_id and frame_index (owner or admin only)

        Note: This endpoint expects frame_index to be passed as a URL parameter or in request data.
        For backward compatibility, extract frame_index from the request body first.
        """
        scene = get_or_404(Scene, scene_id)
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        # Get frame_index from request data
        frame_index = frame_data.pop("frame_index", None)
        if frame_index is None:
            abort(400, message="frame_index is required")

        frame = Frame.query.filter_by(scene_id=scene_id, frame_index=frame_index).first_or_404()

        if "pixel_data" in frame_data:
            frame.pixel_data = frame_data["pixel_data"]
        if "duration" in frame_data:
            frame.duration = frame_data["duration"]
        if "brightness" in frame_data:
            frame.brightness = frame_data["brightness"]
        if "color_r" in frame_data:
            frame.color_r = frame_data["color_r"]
        if "color_g" in frame_data:
            frame.color_g = frame_data["color_g"]
        if "color_b" in frame_data:
            frame.color_b = frame_data["color_b"]

        db.session.commit()
        return frame


@blp.route("/frames/<int:frame_id>")
class FrameDetail(MethodView):
    @blp.response(200, frame_schema)
    def get(self, frame_id):
        """Get frame details"""
        frame = get_or_404(Frame, frame_id)
        return frame

    @require_auth
    @blp.arguments(frame_update_schema)
    @blp.response(200, frame_schema)
    def patch(self, frame_data, frame_id):
        """Update frame (owner or admin only)"""
        frame = get_or_404(Frame, frame_id)
        scene = frame.scene
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        if "pixel_data" in frame_data:
            frame.pixel_data = frame_data["pixel_data"]
        if "duration" in frame_data:
            frame.duration = frame_data["duration"]
        if "brightness" in frame_data:
            frame.brightness = frame_data["brightness"]
        if "color_r" in frame_data:
            frame.color_r = frame_data["color_r"]
        if "color_g" in frame_data:
            frame.color_g = frame_data["color_g"]
        if "color_b" in frame_data:
            frame.color_b = frame_data["color_b"]

        db.session.commit()
        return frame

    @require_auth
    @blp.response(204)
    def delete(self, frame_id):
        """Delete frame (owner or admin only)"""
        frame = get_or_404(Frame, frame_id)
        scene = frame.scene
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        db.session.delete(frame)
        db.session.commit()


@blp.route("/<int:scene_id>/play")
class ScenePlay(MethodView):
    @blp.response(200)
    def post(self, scene_id):
        """Start playing a scene on all assigned devices (any user)"""
        scene = get_or_404(Scene, scene_id)

        if not scene.devices or len(scene.devices) == 0:
            abort(
                400,
                message="Scene has no assigned devices. Please select at least one device before playing.",
            )

        if not scene.frames:
            abort(400, message="Scene has no frames")

        # Use loop_mode from scene (stored in editor)
        loop_mode = scene.loop_mode or "once"
        if loop_mode not in ["once", "loop"]:
            loop_mode = "once"

        # Prepare frames data for playback
        # Include device info with protocol and IP
        devices_info = [
            {
                "ip_address": device.ip_address,
                "communication_protocol": device.communication_protocol or "json_api",
                "matrix_width": device.matrix_width,
                "matrix_height": device.matrix_height,
            }
            for device in scene.devices
        ]
        frames_data = [
            {
                "frame_index": frame.frame_index,
                "pixel_data": frame.pixel_data,
                "duration": frame.duration,
                "brightness": frame.brightness
                or 255,  # Default to full brightness (255) if not set
                "color_r": frame.color_r or 100,  # Red intensity (0-100)
                "color_g": frame.color_g or 100,  # Green intensity (0-100)
                "color_b": frame.color_b or 100,  # Blue intensity (0-100)
            }
            for frame in sorted(scene.frames, key=lambda f: f.frame_index)
        ]

        logger.info(
            f"Scene {scene_id} play initiated: {len(devices_info)} devices, {len(frames_data)} frames"
        )
        for frame_data in frames_data:
            pixels = frame_data["pixel_data"].get("pixels", [])
            logger.info(
                f"  Frame {frame_data['frame_index']}: duration={frame_data['duration']}s, "
                f"brightness={frame_data['brightness']}, "
                f"pixels={len(pixels)}"
            )
            # Log sample colors from this frame to debug missing pixels
            if pixels:
                sample_colors = [tuple(p.get("color", [0, 0, 0])) for p in pixels[:10]]
                logger.debug(
                    f"    Frame {frame_data['frame_index']} sample colors (first 10): {sample_colors}"
                )

        # Start playback in background thread
        start_scene_playback(scene_id, devices_info, frames_data, loop_mode)

        return {
            "scene_id": scene_id,
            "status": "playing",
            "loop_mode": loop_mode,
            "frame_count": len(frames_data),
            "device_count": len(devices_info),
        }


@blp.route("/<int:scene_id>/stop")
class SceneStop(MethodView):
    @blp.response(200)
    def post(self, scene_id):
        """Stop playing a scene on all assigned devices (any user)"""
        scene = get_or_404(Scene, scene_id)

        # Stop background playback
        stop_scene_playback(scene_id)

        # Also ensure devices are turned off (in case playback already finished)
        device_ips = [device.ip_address for device in scene.devices]
        results = {}
        for ip in device_ips:
            results[ip] = DeviceController.turn_off(ip)

        return {
            "scene_id": scene_id,
            "status": "stopped",
            "device_results": results,
        }


@blp.route("/<int:scene_id>/playback-status")
class ScenePlaybackStatus(MethodView):
    @blp.response(200)
    def get(self, scene_id):
        """Get playback status of a scene"""
        scene = get_or_404(Scene, scene_id)
        from flask_module.services.scene_playback import active_playbacks

        playback = active_playbacks.get(scene_id)

        if not playback:
            return {
                "scene_id": scene_id,
                "is_playing": False,
                "loop_mode": scene.loop_mode,
                "frame_count": len(scene.frames),
                "devices": [{"id": d.id, "name": d.name} for d in scene.devices],
            }

        return {
            "scene_id": scene_id,
            "is_playing": playback.is_running,
            "loop_mode": playback.loop_mode,
            "frame_count": len(playback.frames),
            "devices": [{"id": d.id, "name": d.name} for d in scene.devices],
        }


@blp.route("/playback-status")
class AllScenesPlaybackStatus(MethodView):
    @blp.response(200)
    def get(self):
        """Get playback status of all active scenes"""
        from flask_module.services.scene_playback import active_playbacks

        active_scenes = []
        for scene_id, playback in active_playbacks.items():
            scene = db.session.get(Scene, scene_id)
            if scene:
                active_scenes.append(
                    {
                        "scene_id": scene_id,
                        "is_playing": True,
                        "loop_mode": playback.loop_mode,
                        "frame_count": len(scene.frames),
                        "devices": [{"id": d.id, "name": d.name} for d in scene.devices],
                    }
                )

        return active_scenes


@blp.route("/<int:scene_id>/upload-image")
class SceneUploadImage(MethodView):
    @require_auth
    @blp.response(201)
    def post(self, scene_id):
        """Upload an image and convert it to a frame (owner or admin only)"""
        scene = get_or_404(Scene, scene_id)
        user_id = request.headers.get("X-User-Id", 1)
        user = db.session.get(User, user_id)

        # Check permissions
        if scene.created_by != user_id and user.role.value != "admin":
            abort(403, message="You don't have permission to modify this scene")

        if "file" not in request.files:
            abort(400, message="No file provided")

        file = request.files["file"]
        if file.filename == "":
            abort(400, message="No file selected")

        # Save uploaded file temporarily
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "/tmp")
        os.makedirs(upload_folder, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        try:
            # Convert image to pixels
            pixel_data = ImageToPixelConverter.convert_image_to_pixels(
                filepath, scene.matrix_width, scene.matrix_height
            )

            # Create frame from image
            frame_index = len(scene.frames)
            frame = Frame(
                scene_id=scene_id,
                frame_index=frame_index,
                pixel_data=pixel_data,
                duration=scene.default_frame_duration,
            )

            db.session.add(frame)
            db.session.commit()

            return {
                "frame_id": frame.id,
                "frame_index": frame.frame_index,
                "pixel_count": len(pixel_data.get("pixels", [])),
            }
        finally:
            # Clean up uploaded file
            os.remove(filepath)


@blp.route("/<int:scene_id>/test")
class SceneTest(MethodView):
    @blp.response(200)
    def post(self, scene_id):
        """Send test frame to all assigned devices (any user)"""
        scene = get_or_404(Scene, scene_id)

        if not scene.devices:
            abort(400, message="Scene has no assigned devices")

        if not scene.frames:
            abort(400, message="Scene has no frames")

        # Get frame_index from request or use first frame
        frame_index = request.get_json().get("frame_index", 0) if request.get_json() else 0
        frame = Frame.query.filter_by(scene_id=scene_id, frame_index=frame_index).first_or_404()

        # Send test frame to all devices using their configured protocol
        results = {}
        for device in scene.devices:
            try:
                protocol = device.communication_protocol or "json_api"

                # Use appropriate protocol
                if protocol == "udp_dnrgb" or protocol == "udp_warls":
                    # UDP DNRGB (indexed dense RGB, max 489 LEDs per packet)
                    # udp_warls is legacy name, same protocol as udp_dnrgb
                    # Add chain_count and segment_id to pixel_data for multi-chain/multi-segment support
                    pixel_data = (
                        frame.pixel_data.copy() if isinstance(frame.pixel_data, dict) else {}
                    )
                    pixel_data["chain_count"] = getattr(device, "chain_count", 1) or 1
                    pixel_data["segment_id"] = getattr(device, "segment_id", 0) or 0
                    success = DeviceController.send_udp_dnrgb(
                        device.ip_address, pixel_data, brightness=128
                    )
                    results[device.ip_address] = success
                else:
                    # JSON API (default) - HTTP API for small devices
                    wled_command = DeviceController.generate_wled_command(
                        frame.pixel_data, brightness=128, on=True
                    )
                    success = DeviceController.send_command_to_device(
                        device.ip_address, wled_command
                    )
                    results[device.ip_address] = success

            except Exception as e:
                logger.error(f"Error sending test frame to {device.ip_address}: {e}")
                results[device.ip_address] = False

        return {
            "scene_id": scene_id,
            "frame_index": frame.frame_index,
            "device_results": results,
        }
