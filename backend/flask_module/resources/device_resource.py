"""
Device API Resource - CRUD operations for LED devices
"""

import json
import logging
from io import BytesIO

from flask import request, send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from flask_module.db import db, get_or_404
from flask_module.models import Device
from flask_module.schemas import DeviceSchema
from flask_module.services.auth_decorators import require_admin, require_auth

logger = logging.getLogger(__name__)
from flask_module.services.device_controller import DeviceController

blp = Blueprint("devices", __name__, url_prefix="/api/devices", description="Device management")

device_schema = DeviceSchema()
devices_schema = DeviceSchema(many=True)


@blp.route("/")
class DeviceList(MethodView):
    @require_auth
    @blp.response(200, devices_schema)
    def get(self):
        """List all devices (requires authentication)"""
        devices = Device.query.all()
        return devices

    @require_admin
    @blp.arguments(device_schema)
    @blp.response(201, device_schema)
    def post(self, device_data):
        """Create a new device (admin only)"""
        # Check if device with this IP already exists
        existing = Device.query.filter_by(ip_address=device_data["ip_address"]).first()
        if existing:
            abort(400, message=f"Device with IP {device_data['ip_address']} already exists")

        device = Device(**device_data)
        # Always create as active - health status is checked separately via /health endpoint
        device.is_active = True

        db.session.add(device)
        db.session.commit()
        return device


@blp.route("/<int:device_id>")
class DeviceDetail(MethodView):
    @require_auth
    @blp.response(200, device_schema)
    def get(self, device_id):
        """Get device details (requires authentication)"""
        device = get_or_404(Device, device_id)
        return device

    @require_admin
    @blp.arguments(device_schema)
    @blp.response(200, device_schema)
    def patch(self, device_data, device_id):
        """Update device (admin only)"""
        device = get_or_404(Device, device_id)

        # Update device with provided data
        # Note: is_active is user-controlled, not automatically set based on health
        for key, value in device_data.items():
            setattr(device, key, value)

        db.session.commit()
        return device

    @require_admin
    @blp.response(204)
    def delete(self, device_id):
        """Delete device (admin only)"""
        device = get_or_404(Device, device_id)
        db.session.delete(device)
        db.session.commit()


@blp.route("/<int:device_id>/health")
class DeviceHealth(MethodView):
    @blp.response(200)
    def get(self, device_id):
        """Check device health"""
        device = get_or_404(Device, device_id)
        is_healthy = DeviceController.check_device_health(device.ip_address)
        return {"device_id": device_id, "ip_address": device.ip_address, "healthy": is_healthy}


@blp.route("/<int:device_id>/test")
class DeviceTest(MethodView):
    @blp.response(200)
    def post(self, device_id):
        """Send a test command to device using its configured protocol"""
        device = get_or_404(Device, device_id)
        protocol = device.communication_protocol or "json_api"

        try:
            # Create a simple white test pattern (all pixels white)
            total_leds = device.matrix_width * device.matrix_height
            chain_count = getattr(device, "chain_count", 1) or 1  # Default to 1 if not set
            segment_id = getattr(device, "segment_id", 0) or 0  # Default to 0 if not set
            pixel_data = {
                "pixels": [{"index": i, "color": [255, 255, 255]} for i in range(total_leds)],
                "width": device.matrix_width,
                "height": device.matrix_height,
                "chain_count": chain_count,
                "segment_id": segment_id,
            }

            logger.info(
                f"DeviceTest: Sending {total_leds} white pixels ({device.matrix_width}x{device.matrix_height}) "
                f"to {device.ip_address} via {protocol}, chains={chain_count}"
            )

            # Send using appropriate protocol
            if protocol == "udp_dnrgb":
                # UDP DNRGB mode (indexed dense RGB with start position)
                # Max 489 LEDs per packet, multiple packets for larger devices
                # Supports multi-chain devices
                success = DeviceController.send_udp_dnrgb(
                    device.ip_address, pixel_data, brightness=255
                )
            elif protocol == "udp_warls":
                # UDP WARLS mode (backward compat - same as DNRGB now)
                success = DeviceController.send_udp_dnrgb(
                    device.ip_address, pixel_data, brightness=255
                )
            else:
                # JSON API (default) - use set_color for simple white
                success = DeviceController.set_color(device.ip_address, 255, 255, 255)

            return {"device_id": device_id, "success": success}

        except Exception as e:
            from flask_smorest import abort as abort_error

            abort_error(500, message=f"Test failed: {str(e)}")


@blp.route("/<int:device_id>/test-n-leds")
class DeviceTestNLEDs(MethodView):
    @blp.response(200)
    def post(self, device_id):
        """Test with N LEDs - useful for debugging device limits.

        Query parameter: count=N (number of LEDs to test)
        Example: /api/devices/2/test-n-leds?count=1024
        """
        device = get_or_404(Device, device_id)
        protocol = device.communication_protocol or "json_api"

        # Get optional query parameter for number of LEDs to test
        num_leds = request.args.get("count", type=int, default=None)
        if num_leds is None:
            num_leds = device.matrix_width * device.matrix_height

        try:
            # Create white test pattern for specified number of LEDs
            chain_count = getattr(device, "chain_count", 1) or 1  # Default to 1 if not set
            segment_id = getattr(device, "segment_id", 0) or 0  # Default to 0 if not set
            pixel_data = {
                "pixels": [{"index": i, "color": [255, 255, 255]} for i in range(num_leds)],
                "width": device.matrix_width,
                "height": device.matrix_height,
                "chain_count": chain_count,
                "segment_id": segment_id,
            }

            logger.info(
                f"DeviceTestNLEDs: Sending {num_leds} white pixels to {device.ip_address} "
                f"via {protocol}, chains={chain_count}"
            )

            # Send using appropriate protocol
            if protocol == "udp_dnrgb" or protocol == "udp_warls":
                success = DeviceController.send_udp_dnrgb(
                    device.ip_address, pixel_data, brightness=255
                )
            else:
                success = DeviceController.set_color(device.ip_address, 255, 255, 255)

            return {"device_id": device_id, "num_leds_sent": num_leds, "success": success}

        except Exception as e:
            from flask_smorest import abort as abort_error

            abort_error(500, message=f"Test failed: {str(e)}")


@blp.route("/<int:device_id>/off")
class DeviceOff(MethodView):
    @blp.response(200)
    def post(self, device_id):
        """Turn off device"""
        device = get_or_404(Device, device_id)
        success = DeviceController.turn_off(device.ip_address)
        return {"device_id": device_id, "success": success}


@blp.route("/<int:device_id>/send-frame")
class DeviceSendFrame(MethodView):
    @blp.response(200)
    def post(self, device_id):
        """Send a frame (with pixel data) to device using appropriate protocol"""
        device = get_or_404(Device, device_id)

        # Get pixel_data from request body
        data = request.get_json() or {}
        pixel_data = data.get("pixel_data", {"pixels": [], "width": 16, "height": 16})
        brightness = data.get("brightness", 255)

        # Send via appropriate protocol based on device configuration
        if device.communication_protocol == Device.PROTOCOL_UDP_DNRGB:
            # Use UDP DNRGB for high-speed, unlimited LED support
            success = DeviceController.send_udp_dnrgb(device.ip_address, pixel_data, brightness)
        else:
            # Use JSON API (HTTP) for smaller devices
            command = DeviceController.generate_wled_command(
                pixel_data, brightness=brightness, on=True
            )
            success = DeviceController.send_command_to_device(device.ip_address, command)

        return {"device_id": device_id, "success": success}


@blp.route("/<int:device_id>/send-frame-timed")
class DeviceSendFrameTimed(MethodView):
    @blp.response(200)
    def post(self, device_id):
        """Send a frame to device and auto turn-off after specified time"""
        import threading
        import time

        from flask_module.services.scene_playback import upscale_pixel_data

        device = get_or_404(Device, device_id)

        # Get pixel_data from request body
        data = request.get_json() or {}
        pixel_data = data.get("pixel_data", {"pixels": [], "width": 16, "height": 16})
        brightness = data.get("brightness", 128)
        auto_off_delay = data.get("auto_off_delay", 5)  # Default 5 seconds
        # Optional per-frame RGB multipliers (0-100)
        color_r = data.get("color_r", 10)
        color_g = data.get("color_g", 10)
        color_b = data.get("color_b", 10)

        # Upscale pixel data if device resolution differs from scene
        upscaled_pixel_data = upscale_pixel_data(
            pixel_data, device.matrix_width, device.matrix_height
        )

        # Send via appropriate protocol based on device configuration
        if device.communication_protocol == Device.PROTOCOL_UDP_DNRGB:
            # Use UDP DNRGB for high-speed, unlimited LED support
            success = DeviceController.send_udp_dnrgb(
                device.ip_address,
                upscaled_pixel_data,
                brightness,
                color_r=color_r,
                color_g=color_g,
                color_b=color_b,
            )
        else:
            # Use JSON API (HTTP) for smaller devices
            command = DeviceController.generate_wled_command(
                upscaled_pixel_data,
                brightness,
                on=True,
                color_r=color_r,
                color_g=color_g,
                color_b=color_b,
            )
            success = DeviceController.send_command_to_device(device.ip_address, command)

        # Schedule auto turn-off in background thread
        def turn_off_later():
            time.sleep(auto_off_delay)
            DeviceController.turn_off(device.ip_address)
            # Logging ohne current_app (thread-safe)
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Device {device.ip_address} turned off after {auto_off_delay}s")

        thread = threading.Thread(target=turn_off_later, daemon=True)
        thread.start()

        return {
            "device_id": device_id,
            "success": success,
            "auto_off_delay": auto_off_delay,
        }


@blp.route("/export")
class DeviceExport(MethodView):
    @require_admin
    @blp.response(200)
    def get(self):
        """Export all devices as JSON file"""
        devices = Device.query.all()
        devices_data = devices_schema.dump(devices)

        # Create JSON file in memory
        json_str = json.dumps(devices_data, indent=2, default=str)
        json_bytes = json_str.encode("utf-8")

        # Return as downloadable file
        return send_file(
            BytesIO(json_bytes),
            mimetype="application/json",
            as_attachment=True,
            download_name="devices_export.json",
        )


@blp.route("/import", methods=["POST"])
class DeviceImport(MethodView):
    @require_admin
    def post(self):
        """Import devices from JSON file"""
        # Check if file is in request
        if "file" not in request.files:
            abort(400, message="No file provided")

        file = request.files["file"]

        if file.filename == "":
            abort(400, message="No file selected")

        if not file.filename.endswith(".json"):
            abort(400, message="File must be JSON format")

        try:
            # Read and parse JSON
            content = file.read().decode("utf-8")
            devices_data = json.loads(content)

            # Ensure it's a list
            if not isinstance(devices_data, list):
                devices_data = [devices_data]

            imported_count = 0
            errors = []

            for device_data in devices_data:
                try:
                    # Validate required fields
                    if "ip_address" not in device_data or "name" not in device_data:
                        errors.append("Missing required fields (ip_address or name)")
                        continue

                    # Check if device with this IP already exists
                    existing = Device.query.filter_by(
                        ip_address=device_data.get("ip_address")
                    ).first()

                    if existing:
                        errors.append(
                            f"Device with IP {device_data.get('ip_address')} already exists"
                        )
                        continue

                    # Remove id and timestamp fields (let DB generate them)
                    device_data.pop("id", None)
                    device_data.pop("created_at", None)
                    device_data.pop("updated_at", None)

                    # Ensure all new fields have defaults if not present
                    device_data.setdefault("matrix_width", 16)
                    device_data.setdefault("matrix_height", 16)
                    device_data.setdefault("communication_protocol", "json_api")
                    device_data.setdefault("chain_count", 1)
                    device_data.setdefault("segment_id", 0)
                    device_data.setdefault("is_active", True)

                    # Create new device
                    device = Device(**device_data)
                    db.session.add(device)
                    imported_count += 1

                except Exception as e:
                    errors.append(f"Error importing device: {str(e)}")

            # Commit all devices at once
            if imported_count > 0:
                db.session.commit()

            return {
                "imported": imported_count,
                "total": len(devices_data),
                "errors": errors if errors else None,
            }, 200

        except json.JSONDecodeError:
            abort(400, message="Invalid JSON format")
        except Exception as e:
            abort(400, message=f"Import failed: {str(e)}")
