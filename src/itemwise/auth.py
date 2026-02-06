"""Authentication utilities for JWT tokens and password hashing."""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Dummy hash for constant-time comparison when user doesn't exist
# This prevents timing attacks that could enumerate valid emails
DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.F3z3z3z3z3z3z3"

# JWT settings
_DEFAULT_SECRET_KEY = "dev-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days


class SecretKeyError(Exception):
    """Raised when SECRET_KEY is not properly configured for production."""

    pass


def _get_secret_key() -> str:
    """Get the SECRET_KEY with security checks.

    Raises:
        SecretKeyError: If SECRET_KEY is not set in production environment.

    Returns:
        The configured secret key.
    """
    secret_key = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY))
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower()
    is_production = env in ("production", "prod")

    # Check if using default key
    if secret_key == _DEFAULT_SECRET_KEY:
        if is_production or not debug_mode:
            raise SecretKeyError(
                "SECRET_KEY must be set to a secure value in production. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        else:
            logger.warning(
                "Using default SECRET_KEY. This is insecure and should only be used for development. "
                "Set SECRET_KEY or JWT_SECRET_KEY environment variable for production."
            )

    return secret_key


# Validate and get SECRET_KEY at module load time
SECRET_KEY = _get_secret_key()


class TokenData(BaseModel):
    """Data stored in JWT token."""

    user_id: int
    email: str


class Token(BaseModel):
    """Token response model with access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """Response model for token refresh endpoint."""

    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh endpoint."""

    refresh_token: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character (!@#$%^&*(),.?":{}|<>)

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, ""


def create_access_token(
    user_id: int, email: str, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's database ID
        email: The user's email
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    user_id: int, email: str, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token with longer expiry.

    Args:
        user_id: The user's database ID
        email: The user's email
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id = int(payload.get("sub", 0))
        email = payload.get("email", "")

        if user_id == 0:
            return None

        return TokenData(user_id=user_id, email=email)
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT refresh token.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid refresh token, None if invalid, expired, or wrong type
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify this is a refresh token
        if payload.get("type") != "refresh":
            return None

        user_id = int(payload.get("sub", 0))
        email = payload.get("email", "")

        if user_id == 0:
            return None

        return TokenData(user_id=user_id, email=email)
    except JWTError:
        return None
