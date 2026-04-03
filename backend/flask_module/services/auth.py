"""
Authentication and authorization utilities
"""

from functools import wraps

from flask import abort, request

from flask_module.db import db, get_or_404
from flask_module.models import User, UserRole


def require_auth(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for user ID in header (simplified for now)
        # In production, this would check JWT tokens
        user_id = request.headers.get("X-User-Id")

        if not user_id:
            abort(401, message="Authentication required")

        try:
            user = db.session.get(User, int(user_id))
            if not user or not user.is_active:
                abort(401, message="Invalid or inactive user")
        except (ValueError, TypeError):
            abort(401, message="Invalid user ID")

        # Store user in request context for later use
        request.current_user = user
        return f(*args, **kwargs)

    return decorated_function


def require_role(required_role):
    """Decorator to require specific role"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = request.headers.get("X-User-Id")

            if not user_id:
                abort(401, message="Authentication required")

            try:
                user = db.session.get(User, int(user_id))
                if not user or not user.is_active:
                    abort(401, message="Invalid or inactive user")

                # Check if user has required role
                if user.role.value != required_role:
                    abort(403, message=f"This action requires {required_role} role")

                request.current_user = user
            except (ValueError, TypeError):
                abort(401, message="Invalid user ID")

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_scene_ownership(f):
    """Decorator to check if user owns the scene"""

    @wraps(f)
    def decorated_function(scene_id, *args, **kwargs):
        from flask_module.models import Scene

        user_id = request.headers.get("X-User-Id")
        if not user_id:
            abort(401, message="Authentication required")

        scene = get_or_404(Scene, scene_id)

        user = db.session.get(User, int(user_id))
        if not user or (scene.created_by != user.id and user.role != UserRole.ADMIN):
            abort(403, message="You don't have permission to modify this scene")

        request.current_user = user
        return f(scene_id, *args, **kwargs)

    return decorated_function
