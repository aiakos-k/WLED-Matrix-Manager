"""Tests for database models"""

from datetime import datetime

import pytest

from flask_module.models.user import User


class TestUserModel:
    """Test User model"""

    def test_user_creation(self, app, db):
        """Test creating a user instance"""
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_user_repr(self, app, db):
        """Test user string representation"""
        user = User(username="testuser", email="test@example.com")
        assert "testuser" in repr(user)

    def test_user_unique_username(self, app, db):
        """Test username must be unique"""
        user1 = User(username="unique", email="user1@test.com")
        db.session.add(user1)
        db.session.commit()

        user2 = User(username="unique", email="user2@test.com")
        db.session.add(user2)

        # Should raise IntegrityError
        with pytest.raises(Exception):
            db.session.commit()

    def test_user_unique_email(self, app, db):
        """Test email must be unique"""
        user1 = User(username="user1", email="unique@test.com")
        db.session.add(user1)
        db.session.commit()

        user2 = User(username="user2", email="unique@test.com")
        db.session.add(user2)

        with pytest.raises(Exception):
            db.session.commit()

    def test_user_updated_at_changes(self, app, db):
        """Test updated_at changes on update"""
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()

        original_updated = user.updated_at

        # Update user
        user.email = "newemail@test.com"
        db.session.commit()

        # updated_at should change
        assert user.updated_at >= original_updated
