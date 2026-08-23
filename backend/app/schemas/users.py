from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import UserResponse


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role_name: str = Field(pattern="^(SUPER-ADMIN|ADMIN)$")


class SetUserActiveRequest(BaseModel):
    is_active: bool


class AssignRoleRequest(BaseModel):
    role_name: str = Field(pattern="^(SUPER-ADMIN|ADMIN)$")


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    offset: int
    limit: int
