from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.models.auth import User
from app.repositories.user_repository import UserRepository


class AuthenticationService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def authenticate(self, email: str, password: str) -> tuple[User, str]:
        user = await self.repository.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AppError(401, "invalid_credentials", "Invalid email or password.")
        token = create_access_token(str(user.id), {"tv": user.token_version})
        return user, token
