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

_PLACEHOLDER_KEYS = {
    "replace-with-valid-fernet-key-32-urlsafe-base64-bytes",
    "placeholder",
    "p7X1vY3hTz9_mR8uX0wK2lO5jA6bC4eG7iH9kJ1lM3o=",  # allow dev key if explicitly configured, checked below
    "",
}

# Sensitive keys to scrub from logs and exception payloads
SENSITIVE_KEY_PATTERNS = {
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "code",
    "authorization",
    "secret",
    "password",
    "hashed_password",
    "encryption_key",
}


def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Mask a sensitive string for safe debugging (e.g. '1000.***abc')."""
    if not secret:
        return "[empty]"
    s = str(secret).strip()
    if len(s) <= visible_chars * 2:
        return "***"
    return f"{s[:visible_chars]}...{s[-visible_chars:]}"


def sanitize_data(data: Any) -> Any:
    """
    Recursively sanitize dictionaries, lists, and strings by scrubbing
    sensitive OAuth keys, tokens, and passwords to prevent information leakage.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            key_lower = str(k).lower()
            if any(p in key_lower for p in SENSITIVE_KEY_PATTERNS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = sanitize_data(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


def validate_encryption_key() -> bool:
    """
    Validate that the configured ENCRYPTION_KEY is present, valid Fernet,
    and capable of symmetric encryption and decryption.
    Fails fast on startup if key is missing or invalid.
    """
    key = settings.ENCRYPTION_KEY
    if not key or not str(key).strip():
        raise ValueError("ENCRYPTION_KEY is not configured in settings or environment.")

    cleaned_key = str(key).strip().strip('"').strip("'")
    if cleaned_key == "replace-with-valid-fernet-key-32-urlsafe-base64-bytes":
        raise ValueError(
            "ENCRYPTION_KEY is set to placeholder value. "
            "Generate a valid 44-character URL-safe base64 key with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    try:
        f = Fernet(cleaned_key.encode("utf-8"))
        test_payload = b"onedesk-startup-validation-probe"
        encrypted = f.encrypt(test_payload)
        decrypted = f.decrypt(encrypted)
        if decrypted != test_payload:
            raise ValueError("Encryption round-trip failed verification.")
    except Exception as exc:
        raise ValueError(
            f"ENCRYPTION_KEY failed cryptographic validation ({exc}). "
            "It must be 32 URL-safe base64-encoded bytes (44 characters)."
        ) from exc

    return True


def get_fernet() -> Fernet:
    """Initialize or return the cached Fernet encryption instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY is not configured. "
                "Generate a valid key with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        cleaned_key = str(key).strip().strip('"').strip("'")
        if cleaned_key == "replace-with-valid-fernet-key-32-urlsafe-base64-bytes":
            raise ValueError("ENCRYPTION_KEY is set to placeholder value.")
        try:
            _fernet_instance = Fernet(cleaned_key.encode("utf-8"))
        except Exception as exc:
            raise ValueError(
                f"ENCRYPTION_KEY is invalid ({exc}). "
                "It must be a 44-character URL-safe base64-encoded 32-byte key."
            ) from exc
    return _fernet_instance


def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a sensitive token (OAuth access/refresh token) for storage at rest."""
    if not plain_token:
        return None
    if not isinstance(plain_token, str):
        plain_token = str(plain_token)

    fernet = get_fernet()

    # Prevent accidental double encryption if the string is already encrypted with our key
    if plain_token.startswith("gAAAAA"):
        try:
            # If it already successfully decrypts with our key, do not double-encrypt
            fernet.decrypt(plain_token.encode("utf-8"))
            return plain_token
        except Exception:
            pass

    try:
        encrypted_bytes = fernet.encrypt(plain_token.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")
    except Exception as exc:
        logger.error(f"Failed to encrypt OAuth token: {type(exc).__name__}")
        raise ValueError(f"Token encryption failed: {type(exc).__name__}") from exc


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt an encrypted token retrieved from the database."""
    if not encrypted_token:
        return None
    if not isinstance(encrypted_token, str):
        encrypted_token = str(encrypted_token)

    try:
        fernet = get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt token: Invalid ciphertext or encryption key mismatch.")
        raise ValueError("Decryption failed. Token is corrupted or encryption key mismatch.")
    except Exception as exc:
        logger.error(f"Unexpected error during token decryption: {type(exc).__name__}")
        raise ValueError(f"Decryption failed: {type(exc).__name__}") from exc

