"""Integration tests for API endpoints"""


class TestUserAPIFlow:
    """Test complete user CRUD flow"""

    def test_complete_user_lifecycle(self, client, db):
        """Test creating, reading, updating, and deleting a user"""
        # Create
        response = client.post(
            "/api/users",
            json={"username": "lifecycle_user", "email": "lifecycle@test.com"},
        )
        assert response.status_code == 201
        user_data = response.get_json()
        user_id = user_data["id"]

        # Read
        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        assert response.get_json()["username"] == "lifecycle_user"

        # Update
        response = client.put(
            f"/api/users/{user_id}",
            json={"username": "updated_user", "email": "updated@test.com"},
        )
        assert response.status_code == 200

        # Verify update
        response = client.get(f"/api/users/{user_id}")
        assert response.get_json()["username"] == "updated_user"

        # Delete
        response = client.delete(f"/api/users/{user_id}")
        assert response.status_code == 204

        # Verify deletion
        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 404

    def test_duplicate_username(self, client, db):
        """Test that duplicate usernames are rejected"""
        client.post(
            "/api/users",
            json={"username": "duplicate", "email": "first@test.com"},
        )

        response = client.post(
            "/api/users",
            json={"username": "duplicate", "email": "second@test.com"},
        )
        assert response.status_code in [409, 422, 500]

    def test_duplicate_email(self, client, db):
        """Test that duplicate emails are rejected"""
        client.post(
            "/api/users",
            json={"username": "user1", "email": "duplicate@test.com"},
        )

        response = client.post(
            "/api/users",
            json={"username": "user2", "email": "duplicate@test.com"},
        )
        assert response.status_code in [409, 422, 500]


class TestAPIDocumentation:
    """Test API documentation endpoints"""

    def test_swagger_ui_available(self, client):
        """Test Swagger UI is accessible"""
        response = client.get("/swagger-ui")
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling"""

    def test_404_for_nonexistent_user(self, client):
        """Test 404 for non-existent user"""
        response = client.get("/api/users/99999")
        assert response.status_code == 404

    def test_invalid_json(self, client):
        """Test invalid JSON is rejected"""
        response = client.post(
            "/api/users",
            data="invalid json",
            content_type="application/json",
        )
        assert response.status_code in [400, 415, 422]

    def test_missing_required_fields(self, client):
        """Test missing required fields"""
        response = client.post("/api/users", json={"username": "only_username"})
        assert response.status_code == 422

    def test_404_error_handler(self, client):
        """Test global 404 error handler"""
        response = client.get("/this-route-does-not-exist")
        assert response.status_code == 404
        data = response.get_json()
        assert "message" in data
        assert "not found" in data["message"].lower()


class TestPagination:
    """Test pagination"""

    def test_list_users_empty(self, client, db):
        """Test listing users when database is empty"""
        response = client.get("/api/users")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_multiple_users(self, client, db):
        """Test listing multiple users"""
        for i in range(3):
            client.post(
                "/api/users",
                json={"username": f"user{i}", "email": f"user{i}@test.com"},
            )

        response = client.get("/api/users")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3
