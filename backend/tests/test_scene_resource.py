"""Tests for scene resource API endpoints"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from flask_module.models.scene import Frame, Scene
from flask_module.models.user import User, UserRole


class TestSceneResource:
    """Test scene API endpoints"""

    def test_list_scenes(self, client, app, db):
        """Test listing all active scenes"""
        with app.app_context():
            # Create test user
            user = User(username="testuser", email="test@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create test scenes
            scene1 = Scene(
                name="Scene 1",
                unique_id="scene1",
                matrix_width=16,
                matrix_height=16,
                created_by=user_id,
                is_active=True,
            )
            scene2 = Scene(
                name="Scene 2",
                unique_id="scene2",
                matrix_width=32,
                matrix_height=32,
                created_by=user_id,
                is_active=True,
            )
            scene3 = Scene(
                name="Inactive Scene",
                unique_id="scene3",
                matrix_width=16,
                matrix_height=16,
                created_by=user_id,
                is_active=False,
            )
            db.session.add_all([scene1, scene2, scene3])
            db.session.commit()

        # List scenes
        response = client.get("/api/scenes/")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data) == 2  # Only active scenes
        assert any(s["name"] == "Scene 1" for s in data)
        assert any(s["name"] == "Scene 2" for s in data)
        assert not any(s["name"] == "Inactive Scene" for s in data)

    def test_create_scene(self, client, app, db):
        """Test creating a new scene"""
        with app.app_context():
            # Create test user
            user = User(username="creator", email="creator@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        scene_data = {
            "name": "New Scene",
            "unique_id": "new_scene_123",
            "description": "Test scene",
            "matrix_width": 32,
            "matrix_height": 32,
            "default_frame_duration": 3.0,
            "loop_mode": "loop",
        }

        response = client.post(
            "/api/scenes/",
            json=scene_data,
            headers={"X-User-Id": str(user_id)},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Scene"
        assert data["unique_id"] == "new_scene_123"
        assert data["matrix_width"] == 32
        assert data["matrix_height"] == 32

        # Verify default frame was created
        with app.app_context():
            scene = Scene.query.filter_by(unique_id="new_scene_123").first()
            assert scene is not None
            frames = Frame.query.filter_by(scene_id=scene.id).all()
            assert len(frames) == 1
            assert frames[0].frame_index == 0

    def test_create_scene_duplicate_unique_id(self, client, app, db):
        """Test creating scene with duplicate unique_id fails"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create existing scene
            scene = Scene(
                name="Existing",
                unique_id="duplicate_id",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()

        scene_data = {
            "name": "New Scene",
            "unique_id": "duplicate_id",
        }

        response = client.post(
            "/api/scenes/",
            json=scene_data,
            headers={"X-User-Id": str(user_id)},
        )

        assert response.status_code == 400
        assert "already exists" in response.get_json()["message"]

    def test_get_scene(self, client, app, db):
        """Test getting a specific scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Test Scene",
                unique_id="test_scene",
                description="Test description",
                matrix_width=16,
                matrix_height=16,
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

        response = client.get(f"/api/scenes/{scene_id}")
        assert response.status_code == 200

        data = response.get_json()
        assert data["name"] == "Test Scene"
        assert data["unique_id"] == "test_scene"
        assert data["description"] == "Test description"

    def test_update_scene(self, client, app, db):
        """Test updating a scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.ADMIN)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Original Name",
                unique_id="scene_to_update",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

            update_data = {
                "name": "Updated Name",
                "description": "Updated description",
                "default_frame_duration": 10.0,
            }

            response = client.patch(
                f"/api/scenes/{scene_id}",
                json=update_data,
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["name"] == "Updated Name"
            assert data["description"] == "Updated description"
            assert data["default_frame_duration"] == 10.0

    def test_update_scene_unauthorized(self, client, app, db):
        """Test updating scene by non-owner fails"""
        with app.app_context():
            owner = User(username="owner", email="owner@test.com", role=UserRole.USER)
            owner.set_password("password")
            other = User(username="other", email="other@test.com", role=UserRole.USER)
            other.set_password("password")
            db.session.add_all([owner, other])
            db.session.commit()
            owner_id = owner.id
            other_id = other.id

            scene = Scene(
                name="Owner Scene",
                unique_id="owner_scene",
                created_by=owner_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

        update_data = {"name": "Hacked Name"}

        response = client.patch(
            f"/api/scenes/{scene_id}",
            json=update_data,
            headers={"X-User-Id": str(other_id)},
        )

        assert response.status_code == 403

    def test_delete_scene(self, client, app, db):
        """Test deleting a scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.ADMIN)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Scene to Delete",
                unique_id="delete_me",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

            response = client.delete(
                f"/api/scenes/{scene_id}",
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 204

            # Verify scene was deleted
            from flask_module.db import db

            scene = db.session.get(Scene, scene_id)
            assert scene is None

    def test_list_frames(self, client, app, db):
        """Test listing frames for a scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Scene with Frames",
                unique_id="scene_frames",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.flush()

            # Add frames
            frame1 = Frame(
                scene_id=scene.id,
                frame_index=0,
                pixel_data={"pixels": []},
                duration=1.0,
            )
            frame2 = Frame(
                scene_id=scene.id,
                frame_index=1,
                pixel_data={"pixels": []},
                duration=2.0,
            )
            db.session.add_all([frame1, frame2])
            db.session.commit()
            scene_id = scene.id

        response = client.get(f"/api/scenes/{scene_id}/frames")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data) == 2
        assert data[0]["frame_index"] == 0
        assert data[1]["frame_index"] == 1

    def test_create_frame(self, client, app, db):
        """Test creating a frame in a scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.ADMIN)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Scene",
                unique_id="scene_for_frame",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

            frame_data = {
                "frame_index": 0,
                "pixel_data": {"pixels": [{"index": 0, "color": [255, 0, 0]}]},
                "duration": 5.0,
                "brightness": 200,
                "color_r": 80,
                "color_g": 90,
                "color_b": 100,
            }

            response = client.post(
                f"/api/scenes/{scene_id}/frames",
                json=frame_data,
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 201
            data = response.get_json()
            assert data["frame_index"] == 0
            assert data["duration"] == 5.0
            assert data["brightness"] == 200

    def test_update_frame(self, client, app, db):
        """Test updating a frame"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.ADMIN)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Scene",
                unique_id="scene_update_frame",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.flush()

            frame = Frame(
                scene_id=scene.id,
                frame_index=0,
                pixel_data={"pixels": []},
                duration=1.0,
            )
            db.session.add(frame)
            db.session.commit()
            frame_id = frame.id

            update_data = {
                "pixel_data": {"pixels": [{"index": 0, "color": [0, 255, 0]}]},
                "duration": 3.0,
                "brightness": 150,
            }

            response = client.patch(
                f"/api/scenes/frames/{frame_id}",
                json=update_data,
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["duration"] == 3.0
            assert data["brightness"] == 150

    def test_delete_frame(self, client, app, db):
        """Test deleting a frame"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.ADMIN)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Scene",
                unique_id="scene_delete_frame",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.flush()

            frame = Frame(
                scene_id=scene.id,
                frame_index=0,
                pixel_data={"pixels": []},
            )
            db.session.add(frame)
            db.session.commit()
            frame_id = frame.id

            response = client.delete(
                f"/api/scenes/frames/{frame_id}",
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 204

            # Verify frame was deleted
            from flask_module.db import db

            frame = db.session.get(Frame, frame_id)
            assert frame is None

    @patch("flask_module.resources.scene_resource.start_scene_playback")
    def test_play_scene(self, mock_start, client, app, db):
        """Test playing a scene"""
        from flask_module.models import Device

        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Create device
            device = Device(
                name="Test Device",
                ip_address="192.168.1.100",
                matrix_width=16,
                matrix_height=16,
            )
            db.session.add(device)
            db.session.flush()

            # Create scene with device
            scene = Scene(
                name="Playable Scene",
                unique_id="play_scene",
                created_by=user_id,
            )
            scene.devices.append(device)
            db.session.add(scene)
            db.session.flush()

            # Add at least one frame
            frame = Frame(
                scene_id=scene.id,
                frame_index=0,
                pixel_data={"pixels": []},
                duration=1.0,
            )
            db.session.add(frame)
            db.session.commit()
            scene_id = scene.id

            response = client.post(
                f"/api/scenes/{scene_id}/play",
                headers={"X-User-Id": str(user_id)},
            )

            assert response.status_code == 200
            # Verify start_scene_playback was called
            mock_start.assert_called_once()

    @patch("flask_module.resources.scene_resource.stop_scene_playback")
    def test_stop_scene(self, mock_stop, client, app, db):
        """Test stopping a scene"""
        with app.app_context():
            user = User(username="user", email="user@test.com", role=UserRole.USER)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            scene = Scene(
                name="Stoppable Scene",
                unique_id="stop_scene",
                created_by=user_id,
            )
            db.session.add(scene)
            db.session.commit()
            scene_id = scene.id

        response = client.post(
            f"/api/scenes/{scene_id}/stop",
            headers={"X-User-Id": str(user_id)},
        )

        assert response.status_code == 200
        # Verify stop_scene_playback was called
        mock_stop.assert_called_once()
