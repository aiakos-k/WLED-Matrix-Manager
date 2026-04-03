"""Tests for authentication resource API endpoints"""

import pytest

from flask_module.models.user import User, UserRole
from flask_module.services.auth_service import AuthService


class TestAuthResource:
    """Test authentication API endpoints"""

    def test_login_success(self, client, app, db):
        """Test successful login"""
        with app.app_context():
            # Create active user
            user = User(
                username="testuser",
                email="test@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()

            login_data = {"username": "testuser", "password": "password123"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 200
            data = response.get_json()
            assert "token" in data
            assert "user" in data
            assert data["user"]["username"] == "testuser"
            assert data["user"]["email"] == "test@example.com"
            assert "is_admin" in data["user"]

    def test_login_invalid_credentials(self, client, app, db):
        """Test login with wrong password"""
        with app.app_context():
            user = User(
                username="testuser",
                email="test@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()

            login_data = {"username": "testuser", "password": "wrong_password"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 401
            assert "Invalid credentials" in response.get_json()["message"]

    def test_login_nonexistent_user(self, client, app):
        """Test login with non-existent username"""
        with app.app_context():
            login_data = {"username": "nonexistent", "password": "anypassword"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 401

    def test_login_inactive_user(self, client, app, db):
        """Test login with inactive user"""
        with app.app_context():
            user = User(
                username="inactive",
                email="inactive@example.com",
                role=UserRole.USER,
                is_active=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()

            login_data = {"username": "inactive", "password": "password123"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 403
            assert "not approved" in response.get_json()["message"]

    def test_login_missing_username(self, client, app):
        """Test login without username"""
        with app.app_context():
            login_data = {"password": "password123"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 400
            assert "Missing username or password" in response.get_json()["message"]

    def test_login_missing_password(self, client, app):
        """Test login without password"""
        with app.app_context():
            login_data = {"username": "testuser"}

            response = client.post("/api/auth/login", json=login_data)

            assert response.status_code == 400

    def test_login_empty_body(self, client, app):
        """Test login with empty request body"""
        with app.app_context():
            response = client.post("/api/auth/login", json={})

            assert response.status_code == 400

    def test_logout(self, client, app):
        """Test logout endpoint"""
        with app.app_context():
            response = client.post("/api/auth/logout")

            assert response.status_code == 200
            assert "Logout successful" in response.get_json()["message"]

    def test_get_current_user(self, client, app, db):
        """Test getting current user info with valid token"""
        with app.app_context():
            user = User(
                username="tokenuser",
                email="token@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Generate token
            token = AuthService.generate_token(user_id)

            response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

            assert response.status_code == 200
            data = response.get_json()
            assert data["username"] == "tokenuser"
            assert data["email"] == "token@example.com"
            assert "is_admin" in data

    def test_get_current_user_no_token(self, client, app):
        """Test getting current user without token"""
        with app.app_context():
            response = client.get("/api/auth/me")

            assert response.status_code == 401
            assert "No token provided" in response.get_json()["message"]

    def test_get_current_user_invalid_token(self, client, app):
        """Test getting current user with invalid token"""
        with app.app_context():
            response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token"})

            assert response.status_code == 401
            assert "Invalid token" in response.get_json()["message"]

    def test_register_success(self, client, app, db):
        """Test successful user registration"""
        with app.app_context():
            register_data = {
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass123",
            }

            response = client.post("/api/auth/register", json=register_data)

            assert response.status_code == 201
            data = response.get_json()
            assert "Registration successful" in data["message"]
            assert data["user"]["username"] == "newuser"
            assert data["user"]["is_active"] is False  # Requires approval

            # Verify user was created
            user = User.query.filter_by(username="newuser").first()
            assert user is not None
            assert user.is_active is False
            assert user.check_password("securepass123")

    def test_register_duplicate_username(self, client, app, db):
        """Test registration with existing username"""
        with app.app_context():
            # Create existing user
            existing = User(username="existing", email="existing@example.com")
            existing.set_password("password")
            db.session.add(existing)
            db.session.commit()

            register_data = {
                "username": "existing",
                "email": "different@example.com",
                "password": "password123",
            }

            response = client.post("/api/auth/register", json=register_data)

            assert response.status_code == 400
            assert "Username already exists" in response.get_json()["message"]

    def test_register_duplicate_email(self, client, app, db):
        """Test registration with existing email"""
        with app.app_context():
            # Create existing user
            existing = User(username="user1", email="same@example.com")
            existing.set_password("password")
            db.session.add(existing)
            db.session.commit()

            register_data = {
                "username": "user2",
                "email": "same@example.com",
                "password": "password123",
            }

            response = client.post("/api/auth/register", json=register_data)

            assert response.status_code == 400
            assert "Email already exists" in response.get_json()["message"]

    def test_register_missing_fields(self, client, app):
        """Test registration with missing required fields"""
        with app.app_context():
            # Missing password
            response = client.post(
                "/api/auth/register",
                json={"username": "user", "email": "user@example.com"},
            )
            assert response.status_code == 400
            assert "Missing required fields" in response.get_json()["message"]

            # Missing email
            response = client.post(
                "/api/auth/register",
                json={"username": "user", "password": "pass123"},
            )
            assert response.status_code == 400

            # Missing username
            response = client.post(
                "/api/auth/register",
                json={"email": "user@example.com", "password": "pass123"},
            )
            assert response.status_code == 400

    def test_change_password_success(self, client, app, db):
        """Test successful password change"""
        with app.app_context():
            user = User(
                username="changepass",
                email="changepass@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("old_password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Generate token
            token = AuthService.generate_token(user_id)

            change_data = {
                "old_password": "old_password",
                "new_password": "new_secure_password",
            }

            response = client.post(
                "/api/auth/change-password",
                json=change_data,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            assert "Password changed successfully" in response.get_json()["message"]

            # Verify password was changed
            from flask_module.db import db

            user = db.session.get(User, user_id)
            assert user.check_password("new_secure_password")
            assert not user.check_password("old_password")

    def test_change_password_wrong_old_password(self, client, app, db):
        """Test password change with wrong old password"""
        with app.app_context():
            user = User(
                username="user",
                email="user@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("correct_old")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            token = AuthService.generate_token(user_id)

            change_data = {
                "old_password": "wrong_old",
                "new_password": "new_password",
            }

            response = client.post(
                "/api/auth/change-password",
                json=change_data,
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 401
            assert "Invalid old password" in response.get_json()["message"]

    def test_change_password_no_token(self, client, app):
        """Test password change without token"""
        with app.app_context():
            change_data = {
                "old_password": "old",
                "new_password": "new",
            }

            response = client.post("/api/auth/change-password", json=change_data)

            assert response.status_code == 401
            assert "No token provided" in response.get_json()["message"]

    def test_change_password_missing_fields(self, client, app, db):
        """Test password change with missing fields"""
        with app.app_context():
            user = User(username="user", email="user@example.com", is_active=True)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            token = AuthService.generate_token(user_id)

            # Missing new_password
            response = client.post(
                "/api/auth/change-password",
                json={"old_password": "password"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 400

    def test_get_pending_users(self, client, app, db):
        """Test getting pending user registrations (admin)"""
        with app.app_context():
            # Create admin
            admin = User(
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                is_active=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)

            # Create pending users
            pending1 = User(username="pending1", email="p1@example.com", is_active=False)
            pending1.set_password("pass")
            pending2 = User(username="pending2", email="p2@example.com", is_active=False)
            pending2.set_password("pass")

            db.session.add_all([pending1, pending2])
            db.session.commit()
            admin_id = admin.id

            token = AuthService.generate_token(admin_id)

            response = client.get(
                "/api/auth/pending-users",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert "pending_users" in data
            assert len(data["pending_users"]) == 2
            assert any(u["username"] == "pending1" for u in data["pending_users"])
            assert any(u["username"] == "pending2" for u in data["pending_users"])

    def test_get_pending_users_not_admin(self, client, app, db):
        """Test getting pending users as non-admin fails"""
        with app.app_context():
            user = User(
                username="user",
                email="user@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            token = AuthService.generate_token(user_id)

            response = client.get(
                "/api/auth/pending-users",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 403
            assert "Admin access required" in response.get_json()["message"]

    def test_get_pending_users_no_token(self, client, app):
        """Test getting pending users without token"""
        with app.app_context():
            response = client.get("/api/auth/pending-users")

            assert response.status_code == 401

    def test_approve_user(self, client, app, db):
        """Test approving a pending user (admin)"""
        with app.app_context():
            # Create admin
            admin = User(
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                is_active=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)

            # Create pending user
            pending = User(username="pending", email="pending@example.com", is_active=False)
            pending.set_password("password")
            db.session.add(pending)
            db.session.commit()
            admin_id = admin.id
            pending_id = pending.id

            token = AuthService.generate_token(admin_id)

            response = client.post(
                f"/api/auth/approve-user/{pending_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            assert "approved successfully" in response.get_json()["message"]

            # Verify user is now active
            from flask_module.db import db

            user = db.session.get(User, pending_id)
            assert user.is_active is True

    def test_approve_user_not_admin(self, client, app, db):
        """Test approving user as non-admin fails"""
        with app.app_context():
            user = User(
                username="user",
                email="user@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password")
            pending = User(username="pending", email="p@example.com", is_active=False)
            pending.set_password("pass")
            db.session.add_all([user, pending])
            db.session.commit()
            user_id = user.id
            pending_id = pending.id

            token = AuthService.generate_token(user_id)

            response = client.post(
                f"/api/auth/approve-user/{pending_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 403

    def test_approve_already_active_user(self, client, app, db):
        """Test approving already active user fails"""
        with app.app_context():
            admin = User(
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                is_active=True,
            )
            admin.set_password("admin123")
            active = User(username="active", email="active@example.com", is_active=True)
            active.set_password("pass")
            db.session.add_all([admin, active])
            db.session.commit()
            admin_id = admin.id
            active_id = active.id

            token = AuthService.generate_token(admin_id)

            response = client.post(
                f"/api/auth/approve-user/{active_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 400
            assert "already approved" in response.get_json()["message"]

    def test_reject_user(self, client, app, db):
        """Test rejecting a pending user (admin)"""
        with app.app_context():
            admin = User(
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                is_active=True,
            )
            admin.set_password("admin123")
            pending = User(username="pending", email="pending@example.com", is_active=False)
            pending.set_password("password")
            db.session.add_all([admin, pending])
            db.session.commit()
            admin_id = admin.id
            pending_id = pending.id

            token = AuthService.generate_token(admin_id)

            response = client.delete(
                f"/api/auth/reject-user/{pending_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            assert "rejected and deleted" in response.get_json()["message"]

            # Verify user was deleted
            from flask_module.db import db

            user = db.session.get(User, pending_id)
            assert user is None

    def test_reject_user_not_admin(self, client, app, db):
        """Test rejecting user as non-admin fails"""
        with app.app_context():
            user = User(
                username="user",
                email="user@example.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password")
            pending = User(username="pending", email="p@example.com", is_active=False)
            pending.set_password("pass")
            db.session.add_all([user, pending])
            db.session.commit()
            user_id = user.id
            pending_id = pending.id

            token = AuthService.generate_token(user_id)

            response = client.delete(
                f"/api/auth/reject-user/{pending_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 403

    def test_reject_active_user_fails(self, client, app, db):
        """Test rejecting active user fails"""
        with app.app_context():
            admin = User(
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                is_active=True,
            )
            admin.set_password("admin123")
            active = User(username="active", email="active@example.com", is_active=True)
            active.set_password("pass")
            db.session.add_all([admin, active])
            db.session.commit()
            admin_id = admin.id
            active_id = active.id

            token = AuthService.generate_token(admin_id)

            response = client.delete(
                f"/api/auth/reject-user/{active_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 400
            assert "Cannot reject an approved user" in response.get_json()["message"]
