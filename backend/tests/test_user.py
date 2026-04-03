import pytest

from flask_module.models.user import User


def test_create_user(client, db):
    """Test creating a new user"""
    response = client.post(
        "/api/users",
        json={"username": "testuser", "email": "test@example.com"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_get_users(client, db):
    """Test getting all users"""
    user = User(username="testuser", email="test@example.com")
    db.session.add(user)
    db.session.commit()

    response = client.get("/api/users")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["username"] == "testuser"


def test_get_user_by_id(client, db):
    """Test getting a specific user"""
    user = User(username="testuser", email="test@example.com")
    db.session.add(user)
    db.session.commit()

    response = client.get(f"/api/users/{user.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "testuser"


def test_update_user(client, db):
    """Test updating a user"""
    user = User(username="testuser", email="test@example.com")
    db.session.add(user)
    db.session.commit()

    response = client.put(
        f"/api/users/{user.id}",
        json={"username": "updateduser", "email": "updated@example.com"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "updateduser"


def test_delete_user(client, db):
    """Test deleting a user"""
    user = User(username="testuser", email="test@example.com")
    db.session.add(user)
    db.session.commit()
    user_id = user.id

    response = client.delete(f"/api/users/{user_id}")
    assert response.status_code == 204

    response = client.get(f"/api/users/{user_id}")
    assert response.status_code == 404


def test_create_user_invalid_data(client):
    """Test creating user with invalid data"""
    response = client.post(
        "/api/users",
        json={"username": "testuser"},
    )
    assert response.status_code == 422
