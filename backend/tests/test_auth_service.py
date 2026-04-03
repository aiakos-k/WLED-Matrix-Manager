"""Tests for authentication service"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from flask_module.models.user import User, UserRole
from flask_module.services.auth_service import AuthService


class TestAuthService:
    """Test authentication service methods"""

    def test_generate_token(self, app):
        """Test JWT token generation"""
        with app.app_context():
            user_id = 1
            token = AuthService.generate_token(user_id)

            # Verify token can be decoded
            payload = jwt.decode(token, AuthService.SECRET_KEY, algorithms=[AuthService.ALGORITHM])

            assert payload["user_id"] == user_id
            assert "exp" in payload
            assert "iat" in payload

    def test_verify_token_valid(self, app):
        """Test verification of valid token"""
        with app.app_context():
            user_id = 1
            token = AuthService.generate_token(user_id)
            payload = AuthService.verify_token(token)

            assert payload["user_id"] == user_id
            assert "exp" in payload

    def test_verify_token_expired(self, app):
        """Test verification of expired token"""
        with app.app_context():
            user_id = 1
            # Create expired token
            payload = {
                "user_id": user_id,
                "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
                "iat": datetime.utcnow() - timedelta(hours=2),
            }
            expired_token = jwt.encode(
                payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM
            )

            with pytest.raises(ValueError, match="Token has expired"):
                AuthService.verify_token(expired_token)

    def test_verify_token_invalid(self, app):
        """Test verification of invalid token"""
        with app.app_context():
            invalid_token = "invalid.token.here"

            with pytest.raises(ValueError, match="Invalid token"):
                AuthService.verify_token(invalid_token)

    def test_verify_token_wrong_signature(self, app):
        """Test verification of token with wrong signature"""
        with app.app_context():
            user_id = 1
            # Create token with different secret
            payload = {
                "user_id": user_id,
                "exp": datetime.utcnow() + timedelta(hours=1),
                "iat": datetime.utcnow(),
            }
            wrong_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

            with pytest.raises(ValueError, match="Invalid token"):
                AuthService.verify_token(wrong_token)

    def test_get_user_from_token_success(self, app, db):
        """Test getting user from valid token"""
        with app.app_context():
            # Create user
            user = User(
                username="tokenuser",
                email="token@test.com",
                role=UserRole.USER,
                is_active=True,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Generate token
            token = AuthService.generate_token(user_id)

            # Get user from token
            retrieved_user = AuthService.get_user_from_token(token)

            assert retrieved_user is not None
            assert retrieved_user.id == user_id
            assert retrieved_user.username == "tokenuser"

    def test_get_user_from_token_inactive_user(self, app, db):
        """Test getting inactive user from token returns None"""
        with app.app_context():
            # Create inactive user
            user = User(
                username="inactiveuser",
                email="inactive@test.com",
                role=UserRole.USER,
                is_active=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            # Generate token
            token = AuthService.generate_token(user_id)

            # Get user from token should return None for inactive user
            retrieved_user = AuthService.get_user_from_token(token)

            assert retrieved_user is None

    def test_get_user_from_token_nonexistent_user(self, app):
        """Test getting non-existent user from token returns None"""
        with app.app_context():
            # Generate token for non-existent user
            token = AuthService.generate_token(99999)

            # Get user from token should return None
            retrieved_user = AuthService.get_user_from_token(token)

            assert retrieved_user is None

    def test_get_user_from_token_expired(self, app):
        """Test getting user from expired token returns None"""
        with app.app_context():
            user_id = 1
            # Create expired token
            payload = {
                "user_id": user_id,
                "exp": datetime.utcnow() - timedelta(hours=1),
                "iat": datetime.utcnow() - timedelta(hours=2),
            }
            expired_token = jwt.encode(
                payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM
            )

            # Get user from expired token should return None
            retrieved_user = AuthService.get_user_from_token(expired_token)

            assert retrieved_user is None

    def test_get_user_from_token_invalid(self, app):
        """Test getting user from invalid token returns None"""
        with app.app_context():
            invalid_token = "invalid.token.here"

            # Get user from invalid token should return None
            retrieved_user = AuthService.get_user_from_token(invalid_token)

            assert retrieved_user is None

    def test_authenticate_user_success(self, app, db):
        """Test successful user authentication"""
        with app.app_context():
            # Create user
            user = User(username="authuser", email="auth@test.com", role=UserRole.USER)
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()

            # Authenticate with correct credentials
            authenticated = AuthService.authenticate_user("authuser", "correct_password")

            assert authenticated is not None
            assert authenticated.username == "authuser"
            assert authenticated.email == "auth@test.com"

    def test_authenticate_user_wrong_password(self, app, db):
        """Test authentication with wrong password"""
        with app.app_context():
            # Create user
            user = User(username="authuser2", email="auth2@test.com", role=UserRole.USER)
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()

            # Authenticate with wrong password
            authenticated = AuthService.authenticate_user("authuser2", "wrong_password")

            assert authenticated is None

    def test_authenticate_user_nonexistent(self, app):
        """Test authentication with non-existent username"""
        with app.app_context():
            # Authenticate with non-existent user
            authenticated = AuthService.authenticate_user("nonexistent", "any_password")

            assert authenticated is None
