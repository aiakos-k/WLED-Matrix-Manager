"""
TOTP (Time-based One-Time Password) Service
Handles 2FA authentication using TOTP
"""

import io
import logging
from typing import Optional

import pyotp
import qrcode

logger = logging.getLogger(__name__)


class TOTPService:
    """Service for TOTP 2FA operations"""

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret (base32 encoded)

        Returns:
            Base32 encoded secret string (16 characters)
        """
        return pyotp.random_base32()

    @staticmethod
    def generate_provisioning_uri(
        username: str, secret: str, issuer: str = "LED Matrix Manager"
    ) -> str:
        """
        Generate provisioning URI for authenticator apps

        Args:
            username: User's username
            secret: Base32 encoded TOTP secret
            issuer: Application name (default: "LED Matrix Manager")

        Returns:
            otpauth:// URI string
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=issuer)

    @staticmethod
    def generate_qr_code(provisioning_uri: str) -> bytes:
        """
        Generate QR code image for provisioning URI

        Args:
            provisioning_uri: otpauth:// URI from generate_provisioning_uri()

        Returns:
            PNG image as bytes
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert PIL Image to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def verify_token(secret: str, token: str, valid_window: int = 1) -> bool:
        """
        Verify a TOTP token against a secret

        Args:
            secret: Base32 encoded TOTP secret
            token: 6-digit TOTP code from user
            valid_window: Number of time steps to check before/after current (default: 1 = ±30 seconds)

        Returns:
            True if token is valid, False otherwise
        """
        if not secret or not token:
            return False

        try:
            totp = pyotp.TOTP(secret)
            # valid_window=1 allows tokens from 30 seconds before/after current time
            return totp.verify(token, valid_window=valid_window)
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False

    @staticmethod
    def get_current_token(secret: str) -> Optional[str]:
        """
        Get current TOTP token for a secret (mainly for testing)

        Args:
            secret: Base32 encoded TOTP secret

        Returns:
            6-digit TOTP code or None if error
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.now()
        except Exception as e:
            logger.error(f"Error generating TOTP token: {e}")
            return None
