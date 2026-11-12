from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
import jwt

from app.core.config import settings
from app.core.logging import logger


# --- Password Hashing ---
def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


# --- JWT Authentication Tokens ---
def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Generate a signed JWT access token for application authentication."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid or expired JWT token: {e}")
        return None


# --- Token Encryption at Rest (Fernet) ---
_fernet_instance: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Initialize or return the cached Fernet encryption instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY must be configured in settings.")
        # Ensure key is bytes
        if isinstance(key, str):
            key_bytes = key.encode("utf-8")
        else:
            key_bytes = key
        _fernet_instance = Fernet(key_bytes)
    return _fernet_instance


def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a sensitive token (OAuth access/refresh token) for storage at rest."""
    if not plain_token:
        return None
    fernet = get_fernet()
    encrypted_bytes = fernet.encrypt(plain_token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt an encrypted token retrieved from the database."""
    if not encrypted_token:
        return None
    try:
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt token: Invalid encryption token or key mismatch.")
        raise ValueError("Decryption failed. Token is corrupted or encryption key changed.")

