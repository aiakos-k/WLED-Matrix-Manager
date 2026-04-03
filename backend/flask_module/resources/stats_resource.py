"""
Public Statistics API Resource - Aggregated counts for home page
No authentication required - only exposes safe aggregate numbers
"""

import logging

from flask.views import MethodView
from flask_smorest import Blueprint

from flask_module.models import Device, Scene

logger = logging.getLogger(__name__)

blp = Blueprint("stats", __name__, url_prefix="/api/stats", description="Public statistics")


@blp.route("/")
class PublicStats(MethodView):
    @blp.response(200)
    def get(self):
        """
        Get aggregated statistics for public display

        Returns only counts - no sensitive information like IPs, usernames, etc.
        This endpoint is intentionally public to allow home page statistics
        for unauthenticated visitors.
        """
        try:
            # Total counts
            total_scenes = Scene.query.filter_by(is_active=True).count()
            total_devices = Device.query.filter_by(is_active=True).count()

            # Active scenes count (scenes currently playing)
            # Check playback status from scene_playback service
            from flask_module.services.scene_playback import get_all_playback_status

            playback_status = get_all_playback_status()
            logger.debug(f"Playback status: {playback_status}")
            active_scenes = sum(
                1 for status in playback_status.values() if status.get("is_playing")
            )
            logger.debug(f"Active scenes count: {active_scenes}")

            # Active devices count (user-controlled is_active flag)
            active_devices = Device.query.filter_by(is_active=True).count()

            return {
                "total_scenes": total_scenes,
                "active_scenes": active_scenes,
                "total_devices": total_devices,
                "active_devices": active_devices,
            }
        except Exception as e:
            logger.error(f"Failed to fetch public stats: {e}")
            # Return zeros on error instead of failing
            return {"total_scenes": 0, "active_scenes": 0, "total_devices": 0, "active_devices": 0}
