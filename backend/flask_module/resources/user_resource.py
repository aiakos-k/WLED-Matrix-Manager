from flask.views import MethodView
from flask_smorest import Blueprint

from flask_module.db import db, get_or_404
from flask_module.models.user import User, UserRole
from flask_module.schemas.user_schema import UserSchema

blp = Blueprint("users", __name__, description="Operations on users")


@blp.route("/users")
class UserList(MethodView):
    @blp.response(200, UserSchema(many=True))
    def get(self):
        """List all users"""
        return User.query.all()

    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, user_data):
        """Create a new user"""
        # Convert role string to UserRole enum if provided
        if "role" in user_data and isinstance(user_data["role"], str):
            try:
                user_data["role"] = UserRole(user_data["role"])
            except ValueError:
                user_data["role"] = UserRole.USER

        # Extract password if provided
        password = user_data.pop("password", None)

        user = User(**user_data)

        # Set password if provided
        if password:
            user.set_password(password)

        db.session.add(user)
        db.session.commit()
        return user


@blp.route("/users/<int:user_id>")
class UserResource(MethodView):
    @blp.response(200, UserSchema)
    def get(self, user_id):
        """Get a user by ID"""
        return get_or_404(User, user_id)

    @blp.arguments(UserSchema)
    @blp.response(200, UserSchema)
    def put(self, user_data, user_id):
        """Update a user"""
        user = get_or_404(User, user_id)

        # Convert role string to UserRole enum if provided
        if "role" in user_data and isinstance(user_data["role"], str):
            try:
                user_data["role"] = UserRole(user_data["role"])
            except ValueError:
                user_data["role"] = UserRole.USER

        # Extract password if provided
        password = user_data.pop("password", None)

        for key, value in user_data.items():
            setattr(user, key, value)

        # Set password if provided
        if password:
            user.set_password(password)

        db.session.commit()
        return user

    @blp.arguments(UserSchema)
    @blp.response(200, UserSchema)
    def patch(self, user_data, user_id):
        """Partially update a user"""
        user = get_or_404(User, user_id)

        # Convert role string to UserRole enum if provided
        if "role" in user_data and isinstance(user_data["role"], str):
            try:
                user_data["role"] = UserRole(user_data["role"])
            except ValueError:
                user_data["role"] = UserRole.USER

        # Extract password if provided
        password = user_data.pop("password", None)

        for key, value in user_data.items():
            if value is not None:
                setattr(user, key, value)

        # Set password if provided
        if password:
            user.set_password(password)

        db.session.commit()
        return user

    @blp.response(204)
    def delete(self, user_id):
        """Delete a user"""
        user = get_or_404(User, user_id)
        db.session.delete(user)
        db.session.commit()
        return ""
