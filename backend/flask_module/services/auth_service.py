"""Authentication service for JWT token generation and validation"""

import os
from datetime import datetime, timedelta

import jwt

from flask_module.db import db
from flask_module.models.user import User


class AuthService:
    """Handle JWT token generation and validation"""

    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    TOKEN_EXPIRY_HOURS = 24

    @staticmethod
    def generate_token(user_id: int) -> str:
        """Generate JWT token for user"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=AuthService.TOKEN_EXPIRY_HOURS),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, AuthService.SECRET_KEY, algorithm=AuthService.ALGORITHM)
        return token

    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, AuthService.SECRET_KEY, algorithms=[AuthService.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    @staticmethod
    def get_user_from_token(token: str) -> User:
        """Get user object from token"""
        try:
            payload = AuthService.verify_token(token)
            user = db.session.get(User, payload["user_id"])
            if not user or not user.is_active:
                return None
            return user
        except ValueError:
            return None

    @staticmethod
    def authenticate_user(username: str, password: str) -> User:
        """Authenticate user and return user object if valid"""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return user
        return None
