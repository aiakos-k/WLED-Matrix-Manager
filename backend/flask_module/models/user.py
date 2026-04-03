from datetime import datetime
from enum import Enum

from werkzeug.security import check_password_hash, generate_password_hash

from flask_module.db import db


class UserRole(str, Enum):
    """User roles for access control"""

    ADMIN = "admin"
    USER = "user"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))  # Will be used with werkzeug.security
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # TOTP 2FA fields
    totp_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded secret
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    scenes = db.relationship("Scene", backref="creator", lazy=True, foreign_keys="Scene.created_by")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    def is_admin(self):
        """Check if user is admin"""
        return self.role == UserRole.ADMIN

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash"""
        return check_password_hash(self.password_hash, password)
