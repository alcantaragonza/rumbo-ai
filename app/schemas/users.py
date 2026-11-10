from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="user", pattern="^(admin|user)$")
    token_limit: int = Field(default=100_000, ge=0)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None
    token_limit: int | None = Field(default=None, ge=0)
