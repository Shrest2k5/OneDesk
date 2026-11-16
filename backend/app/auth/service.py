from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserLogin, UserRegister
from app.core.config import settings
from app.core.logging import logger
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    """Service encapsulating user registration, authentication, and JWT lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(self, data: UserRegister) -> User:
        """Register a new user account with duplicate email validation."""
        existing_user = await self.user_repo.get_by_email(data.email)
        if existing_user:
            logger.warning(f"Registration failed: Email '{data.email}' already registered.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        hashed_pw = hash_password(data.password)
        new_user = await self.user_repo.create(
            name=data.name,
            email=data.email,
            hashed_password=hashed_pw,
        )
        await self.session.commit()
        logger.info(f"User registered successfully: id={new_user.id}, email={new_user.email}")
        return new_user

    async def authenticate(self, data: UserLogin) -> User:
        """
        Authenticate user credentials and return the user model.

        Distinguishes unknown user from incorrect password:
        - Unknown email: Raises 401 with code 'USER_NOT_FOUND'
        - Incorrect password: Raises 401 with code 'INVALID_CREDENTIALS'

        Security Trade-off Notice:
        Returning 'USER_NOT_FOUND' intentionally allows account existence discovery for the supplied email
        to provide a streamlined user registration onboarding experience. No additional sensitive user
        metadata, password hashes, or internal IDs are disclosed.
        """
        user = await self.user_repo.get_by_email(data.email)
        if not user:
            logger.warning(f"Authentication failed: User with email '{data.email}' not found.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": "No account found with this email address. Please create an account to continue.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(data.password, user.hashed_password):
            logger.warning(f"Authentication failed: Incorrect password for email '{data.email}'.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Incorrect email or password. Please try again.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"User authenticated successfully: id={user.id}")
        return user

    def create_token(self, user: User) -> Token:
        """Generate a signed JWT access token for the authenticated user."""
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=str(user.id),
            expires_delta=expires_delta,
            extra_claims={"email": user.email, "name": user.name},
        )
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

