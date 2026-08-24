from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import UserResponse


class CreateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role_name: str = Field(pattern="^(SUPER-ADMIN|ADMIN)$")
    is_active: bool = True


class SetUserActiveRequest(BaseModel):
    is_active: bool


class AssignRoleRequest(BaseModel):
    role_name: str = Field(pattern="^(SUPER-ADMIN|ADMIN)$")


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)
    reason: str | None = Field(default=None, min_length=1, max_length=500)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    offset: int
    limit: int
