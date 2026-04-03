"""Authentication resource for login/logout/me endpoints"""

import base64
from io import BytesIO

from flask import request, send_file
from flask_smorest import Blueprint, abort

from flask_module.db import db, get_or_404
from flask_module.models.user import User
from flask_module.services.auth_service import AuthService
from flask_module.services.totp_service import TOTPService

blp = Blueprint("auth", __name__, url_prefix="/api/auth", description="Authentication endpoints")


class LoginSchema:
    """Schema for login request"""

    def __init__(self):
        self.username = None
        self.password = None


@blp.route("/login", methods=["POST"])
def login():
    """
    Login with username and password
    If TOTP is enabled, returns totp_required=True and no token
    Client must then call /totp/verify with TOTP code
    """
    data = request.get_json()

    if not data or not data.get("username") or not data.get("password"):
        abort(400, message="Missing username or password")

    user = AuthService.authenticate_user(data["username"], data["password"])

    if not user:
        abort(401, message="Invalid credentials")

    # Check if user is approved by admin
    if not user.is_active:
        abort(403, message="Account not approved. Please wait for admin approval.")

    # Check if TOTP is enabled
    if user.totp_enabled:
        return {
            "totp_required": True,
            "username": user.username,
            "message": "Please enter your 2FA code",
        }, 200

    # TOTP not enabled - proceed with normal login
    token = AuthService.generate_token(user.id)

    return {
        "totp_required": False,
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_admin": user.is_admin(),
            "totp_enabled": user.totp_enabled,
        },
    }, 200


@blp.route("/logout", methods=["POST"])
def logout():
    """Logout user (client should delete token)"""
    # Token-based auth doesn't require server-side logout
    # Client just deletes the token
    return {"message": "Logout successful"}, 200


@blp.route("/me", methods=["GET"])
def get_current_user():
    """Get current logged-in user"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(token)

    if not user:
        abort(401, message="Invalid token")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_admin": user.is_admin(),
        "totp_enabled": user.totp_enabled,
    }, 200


@blp.route("/register", methods=["POST"])
def register():
    """Register new user - requires admin approval"""
    data = request.get_json()

    if not data or not data.get("username") or not data.get("password") or not data.get("email"):
        abort(400, message="Missing required fields: username, password, email")

    # Check if user already exists
    if User.query.filter_by(username=data["username"]).first():
        abort(400, message="Username already exists")

    if User.query.filter_by(email=data["email"]).first():
        abort(400, message="Email already exists")

    # Create new user (inactive until admin approves)
    user = User(username=data["username"], email=data["email"], is_active=False)
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    return {
        "message": "Registration successful. Please wait for admin approval.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "totp_enabled": user.totp_enabled,
        },
    }, 201


@blp.route("/change-password", methods=["POST"])
def change_password():
    """Change password for logged-in user"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(token)

    if not user:
        abort(401, message="Invalid token")

    data = request.get_json()

    if not data or not data.get("old_password") or not data.get("new_password"):
        abort(400, message="Missing required fields: old_password, new_password")

    # Verify old password
    if not user.check_password(data["old_password"]):
        abort(401, message="Invalid old password")

    # Set new password
    user.set_password(data["new_password"])
    db.session.commit()

    return {
        "message": "Password changed successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_admin": user.is_admin(),
        },
    }, 200


@blp.route("/pending-users", methods=["GET"])
def get_pending_users():
    """Get list of pending user registrations (admin only)"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    from flask_module.services.auth_service import AuthService

    user = AuthService.get_user_from_token(token)

    if not user or not user.is_admin():
        abort(403, message="Admin access required")

    # Get all inactive users (pending approval)
    pending_users = User.query.filter_by(is_active=False).all()

    return {
        "pending_users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role.value,
                "created_at": u.created_at.isoformat(),
            }
            for u in pending_users
        ]
    }, 200


@blp.route("/approve-user/<int:user_id>", methods=["POST"])
def approve_user(user_id):
    """Approve a pending user registration (admin only)"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    from flask_module.services.auth_service import AuthService

    admin = AuthService.get_user_from_token(token)

    if not admin or not admin.is_admin():
        abort(403, message="Admin access required")

    user = get_or_404(User, user_id)

    if user.is_active:
        abort(400, message="User is already approved")

    user.is_active = True
    db.session.commit()

    return {
        "message": f"User {user.username} approved successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
        },
    }, 200


@blp.route("/reject-user/<int:user_id>", methods=["DELETE"])
def reject_user(user_id):
    """Reject and delete a pending user registration (admin only)"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    from flask_module.services.auth_service import AuthService

    admin = AuthService.get_user_from_token(token)

    if not admin or not admin.is_admin():
        abort(403, message="Admin access required")

    user = get_or_404(User, user_id)

    if user.is_active:
        abort(400, message="Cannot reject an approved user. Use delete instead.")

    db.session.delete(user)
    db.session.commit()

    return {
        "message": f"User {user.username} registration rejected and deleted",
    }, 200


# ==================== TOTP 2FA Endpoints ====================


@blp.route("/totp/setup", methods=["GET"])
def totp_setup():
    """
    Generate TOTP secret and return QR code for authenticator app setup
    User must be logged in
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(token)

    if not user:
        abort(401, message="Invalid token")

    # Generate new secret (will replace old one when enabled)
    secret = TOTPService.generate_secret()

    # Generate provisioning URI
    provisioning_uri = TOTPService.generate_provisioning_uri(user.username, secret)

    # Generate QR code
    qr_code_bytes = TOTPService.generate_qr_code(provisioning_uri)

    # Convert to base64 for frontend display
    qr_code_base64 = base64.b64encode(qr_code_bytes).decode("utf-8")

    # Return QR code and secret
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "username": user.username,
        "qr_code": qr_code_base64,
    }, 200


@blp.route("/totp/qrcode", methods=["POST"])
def totp_qrcode():
    """
    Return QR code image as PNG for given secret
    Used for displaying QR code in UI
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(token)

    if not user:
        abort(401, message="Invalid token")

    data = request.get_json()
    secret = data.get("secret")

    if not secret:
        abort(400, message="Missing secret")

    provisioning_uri = TOTPService.generate_provisioning_uri(user.username, secret)
    qr_code_bytes = TOTPService.generate_qr_code(provisioning_uri)

    return send_file(
        BytesIO(qr_code_bytes),
        mimetype="image/png",
        as_attachment=False,
        download_name="totp_qr.png",
    )


@blp.route("/totp/enable", methods=["POST"])
def totp_enable():
    """
    Enable TOTP 2FA for user after verifying setup code
    Requires: secret, token (6-digit code from authenticator app)
    """
    auth_token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not auth_token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(auth_token)

    if not user:
        abort(401, message="Invalid token")

    data = request.get_json()
    secret = data.get("secret")
    totp_token = data.get("token")

    if not secret or not totp_token:
        abort(400, message="Missing required fields: secret, token")

    # Verify the TOTP token
    if not TOTPService.verify_token(secret, totp_token):
        abort(400, message="Invalid TOTP code. Please try again.")

    # Save secret and enable TOTP
    user.totp_secret = secret
    user.totp_enabled = True
    db.session.commit()

    return {
        "message": "TOTP 2FA enabled successfully",
        "totp_enabled": True,
    }, 200


@blp.route("/totp/disable", methods=["POST"])
def totp_disable():
    """
    Disable TOTP 2FA for user
    Requires current TOTP token for confirmation
    """
    auth_token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not auth_token:
        abort(401, message="No token provided")

    user = AuthService.get_user_from_token(auth_token)

    if not user:
        abort(401, message="Invalid token")

    if not user.totp_enabled:
        abort(400, message="TOTP is not enabled")

    data = request.get_json()
    totp_token = data.get("token")

    if not totp_token:
        abort(400, message="Missing TOTP token for confirmation")

    # Verify the TOTP token before disabling
    if not TOTPService.verify_token(user.totp_secret, totp_token):
        abort(400, message="Invalid TOTP code")

    # Disable TOTP
    user.totp_enabled = False
    user.totp_secret = None
    db.session.commit()

    return {
        "message": "TOTP 2FA disabled successfully",
        "totp_enabled": False,
    }, 200


@blp.route("/totp/verify", methods=["POST"])
def totp_verify():
    """
    Verify TOTP token during login
    Returns JWT token if verification successful
    Requires: username, totp_token
    """
    data = request.get_json()

    username = data.get("username")
    totp_token = data.get("token")

    if not username or not totp_token:
        abort(400, message="Missing required fields: username, token")

    user = User.query.filter_by(username=username, is_active=True).first()

    if not user:
        abort(401, message="Invalid username")

    if not user.totp_enabled:
        abort(400, message="TOTP is not enabled for this user")

    # Verify TOTP token
    if not TOTPService.verify_token(user.totp_secret, totp_token):
        abort(401, message="Invalid TOTP code")

    # Generate JWT token
    token = AuthService.generate_token(user.id)

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "totp_enabled": user.totp_enabled,
        },
    }, 200
