"""Test configuration and fixtures"""

from unittest.mock import MagicMock

import pytest

# Patch auth decorators BEFORE importing app
import flask_module.services.auth_decorators

flask_module.services.auth_decorators.require_admin = lambda f: f
flask_module.services.auth_decorators.require_auth = lambda f: f

from flask_module.app import app as flask_app
from flask_module.db import db as _db


@pytest.fixture(scope="function")
def app():
    """Create application for testing"""
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Provide database for tests"""
    return _db
