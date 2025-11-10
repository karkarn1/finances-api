"""Schemas package."""

from app.schemas.account import (
    AccountBase,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountWithBalance,
)
from app.schemas.account_value import (
    AccountValueBase,
    AccountValueCreate,
    AccountValueResponse,
    AccountValueUpdate,
)
from app.schemas.auth import (
    Token,
    TokenData,
    TokenPair,
    TokenRefresh,
    UserLogin,
    UserRegister,
)
from app.schemas.financial_institution import (
    FinancialInstitutionBase,
    FinancialInstitutionCreate,
    FinancialInstitutionResponse,
    FinancialInstitutionUpdate,
)
from app.schemas.holding import (
    HoldingBase,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    HoldingWithSecurity,
)
from app.schemas.user import UserBase, UserCreate, UserResponse, UserUpdate

__all__ = [
    # Authentication schemas
    "Token",
    "TokenData",
    "TokenPair",
    "TokenRefresh",
    "UserLogin",
    "UserRegister",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Financial institution schemas
    "FinancialInstitutionBase",
    "FinancialInstitutionCreate",
    "FinancialInstitutionResponse",
    "FinancialInstitutionUpdate",
    # Account schemas
    "AccountBase",
    "AccountCreate",
    "AccountResponse",
    "AccountUpdate",
    "AccountWithBalance",
    # Account value schemas
    "AccountValueBase",
    "AccountValueCreate",
    "AccountValueResponse",
    "AccountValueUpdate",
    # Holding schemas
    "HoldingBase",
    "HoldingCreate",
    "HoldingResponse",
    "HoldingUpdate",
    "HoldingWithSecurity",
]
