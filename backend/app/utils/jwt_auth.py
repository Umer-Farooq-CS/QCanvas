"""
JWT token utilities for authentication.
Handles token creation, verification, and user extraction.
"""
import time
from datetime import datetime, timedelta
from typing import Optional
import jwt
from jwt import PyJWTError
from app.config.settings import settings


# JWT Configuration
ALGORITHM = "HS256"
# Session lifetime comes from settings (env: ACCESS_TOKEN_EXPIRE_MINUTES).
# The frontend refreshes the token while the user is active (POST /api/auth/refresh),
# so this is effectively the maximum idle time before a user must sign in again.
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of data to encode in the token (typically {"sub": user_id})
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token as string
    """
    to_encode = data.copy()
    now = datetime.utcnow()

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # auth_time = original login time; carried through refreshes so a session
    # has an absolute maximum age (see SESSION_MAX_AGE_DAYS).
    now_ts = int(time.time())
    to_encode.setdefault("auth_time", now_ts)
    to_encode.update({"exp": expire, "iat": now_ts})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID if token is valid, None otherwise
    """
    payload = verify_token(token)
    if payload:
        return payload.get("sub")
    return None
