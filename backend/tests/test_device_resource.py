"""Tests for device resource endpoints"""

import json
from io import BytesIO

import pytest

from flask_module.models import Device, User, UserRole


class TestDeviceResource:
    """Test device API endpoints"""

    @pytest.fixture
    def admin_user(self, db, app):
        """Create admin user for testing"""
        with app.app_context():
            user = User(
                username="admin",
                email="admin@test.com",
                role=UserRole.ADMIN,
            )
            user.set_password("admin123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id  # Get id before leaving context
            return user_id

    @pytest.fixture
    def test_device(self, db, app):
        """Create test device"""
        with app.app_context():
            device = Device(
                name="Test Device",
                ip_address="192.168.1.100",
                matrix_width=16,
                matrix_height=16,
                communication_protocol="json_api",
                chain_count=1,
                segment_id=0,
            )
            db.session.add(device)
            db.session.commit()
            device_id = device.id  # Get id before leaving context
            return device_id

    def test_get_devices_list(self, client, admin_user):
        """Test GET /api/devices/"""
        response = client.get("/api/devices/", headers={"X-User-Id": str(admin_user)})

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_create_device(self, client, admin_user):
        """Test POST /api/devices/"""
        device_data = {
            "name": "New Device",
            "ip_address": "192.168.1.200",
            "matrix_width": 32,
            "matrix_height": 32,
            "communication_protocol": "udp_dnrgb",
            "chain_count": 4,
            "segment_id": 0,
        }

        response = client.post(
            "/api/devices/",
            json=device_data,
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Device"
        assert data["ip_address"] == "192.168.1.200"
        assert data["matrix_width"] == 32
        assert data["communication_protocol"] == "udp_dnrgb"
        assert data["chain_count"] == 4

    def test_get_device_by_id(self, client, admin_user, test_device):
        """Test GET /api/devices/<id>"""
        response = client.get(
            f"/api/devices/{test_device}",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Test Device"
        assert data["ip_address"] == "192.168.1.100"

    def test_update_device(self, client, admin_user, test_device):
        """Test PATCH /api/devices/<id>"""
        update_data = {
            "name": "Updated Device",
            "ip_address": "192.168.1.100",  # Include IP (required field)
            "matrix_width": 64,
            "matrix_height": 64,
            "communication_protocol": "udp_dnrgb",
        }

        response = client.patch(
            f"/api/devices/{test_device}",
            json=update_data,
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Updated Device"
        assert data["matrix_width"] == 64
        assert data["communication_protocol"] == "udp_dnrgb"

    def test_delete_device(self, client, admin_user, test_device):
        """Test DELETE /api/devices/<id>"""
        response = client.delete(
            f"/api/devices/{test_device}",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 204

        # Verify device is deleted
        verify_response = client.get(
            f"/api/devices/{test_device}",
            headers={"X-User-Id": str(admin_user)},
        )
        assert verify_response.status_code == 404

    def test_export_devices(self, client, admin_user, test_device):
        """Test GET /api/devices/export"""
        response = client.get(
            "/api/devices/export",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"

        # Parse exported data
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["name"] == "Test Device"

    def test_import_devices(self, client, admin_user, app):
        """Test POST /api/devices/import"""
        devices_data = [
            {
                "name": "Imported Device 1",
                "ip_address": "192.168.1.150",
                "matrix_width": 16,
                "matrix_height": 16,
                "communication_protocol": "json_api",
                "chain_count": 1,
                "segment_id": 0,
            },
            {
                "name": "Imported Device 2",
                "ip_address": "192.168.1.151",
                "matrix_width": 64,
                "matrix_height": 64,
                "communication_protocol": "udp_dnrgb",
                "chain_count": 4,
                "segment_id": 0,
            },
        ]

        # Create JSON file in memory
        json_data = json.dumps(devices_data)
        file_data = BytesIO(json_data.encode("utf-8"))

        response = client.post(
            "/api/devices/import",
            data={"file": (file_data, "devices.json")},
            content_type="multipart/form-data",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["imported"] == 2
        assert data["total"] == 2

    def test_import_devices_duplicate_ip(self, client, admin_user, test_device):
        """Test import with duplicate IP address"""
        devices_data = [
            {
                "name": "Duplicate Device",
                "ip_address": "192.168.1.100",  # Same as test_device
                "matrix_width": 16,
                "matrix_height": 16,
            }
        ]

        json_data = json.dumps(devices_data)
        file_data = BytesIO(json_data.encode("utf-8"))

        response = client.post(
            "/api/devices/import",
            data={"file": (file_data, "devices.json")},
            content_type="multipart/form-data",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["imported"] == 0  # Should not import duplicate
        assert data["errors"] is not None

    def test_import_devices_missing_fields(self, client, admin_user):
        """Test import with missing required fields"""
        devices_data = [{"name": "Invalid Device"}]  # Missing ip_address

        json_data = json.dumps(devices_data)
        file_data = BytesIO(json_data.encode("utf-8"))

        response = client.post(
            "/api/devices/import",
            data={"file": (file_data, "devices.json")},
            content_type="multipart/form-data",
            headers={"X-User-Id": str(admin_user)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["imported"] == 0
        assert data["errors"] is not None
