from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.enums import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.USER
    capital_inr: Decimal = Field(default=Decimal("100000.00"), ge=0)
    risk_per_trade_pct: Decimal = Field(
        default=Decimal("2.00"), ge=Decimal("0.1"), le=Decimal("10")
    )
    daily_loss_limit_pct: Decimal = Field(
        default=Decimal("3.00"), ge=Decimal("0.1"), le=Decimal("20")
    )
    max_trades_per_day: int = Field(default=2, ge=1, le=20)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    capital_inr: Decimal | None = Field(default=None, ge=0)
    risk_per_trade_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.1"), le=Decimal("10")
    )
    daily_loss_limit_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.1"), le=Decimal("20")
    )
    max_trades_per_day: int | None = Field(default=None, ge=1, le=20)
    is_active: bool | None = None
    # role and trading_mode are intentionally absent —
    # role changes require a dedicated admin endpoint;
    # trading_mode changes require the 30-day paper-trading gate.


class AdminUserUpdate(UserUpdate):
    """Extended update schema for admins — allows role changes."""
    role: Role | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    capital_inr: Decimal
    risk_per_trade_pct: Decimal
    daily_loss_limit_pct: Decimal
    max_trades_per_day: int
    is_active: bool
    trading_mode: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AccessTokenResponse(BaseModel):
    """Returned by /auth/refresh — no user payload to avoid stale data."""
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
