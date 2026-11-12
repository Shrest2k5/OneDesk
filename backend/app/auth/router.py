from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.auth.schemas import Token, UserLogin, UserRead, UserRegister
from app.auth.service import AuthService
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserRegister,
    session: AsyncSession = Depends(get_db),
):
    """
    Register a new user in OneDesk with name, email, and password.
    Validates duplicate email and returns the created user entity.
    """
    auth_service = AuthService(session)
    user = await auth_service.register(data)
    return user


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User login with JWT issuance",
)
async def login(
    data: UserLogin,
    session: AsyncSession = Depends(get_db),
):
    """
    Authenticate user credentials (email and password).
    Returns a signed JWT bearer access token.
    """
    auth_service = AuthService(session)
    user = await auth_service.authenticate(data)
    return auth_service.create_token(user)


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve profile details of currently authenticated user.
    Password hash and sensitive internal details are never exposed.
    """
    return current_user

