"""Authentication schemas."""

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """Access token response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    username: str | None = None


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., min_length=1)


class UserRegister(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class TokenRefresh(BaseModel):
    """Schema for refreshing access token."""

    refresh_token: str


class TokenPair(BaseModel):
    """Pair of access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""

    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, description="New password must be at least 8 characters"
    )


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str
