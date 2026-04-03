"""Authorization decorators for protecting routes"""

from functools import wraps

from flask import request
from flask_smorest import abort

from flask_module.services.auth_service import AuthService


def get_token_from_request():
    """Extract JWT token from Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.replace("Bearer ", "")


def require_auth(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()

        if not token:
            abort(401, message="No token provided. Please login first.")

        user = AuthService.get_user_from_token(token)

        if not user:
            abort(401, message="Invalid or expired token")

        # Pass user to the route handler
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """Decorator to require admin role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()

        if not token:
            abort(401, message="No token provided. Please login first.")

        user = AuthService.get_user_from_token(token)

        if not user:
            abort(401, message="Invalid or expired token")

        if not user.is_admin():
            abort(403, message="Admin access required")

        # Pass user to the route handler
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function
