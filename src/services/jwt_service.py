from uuid import UUID

from ..utils import singleton


@singleton
class JWTService:
    def get_user_id(self, token: str) -> UUID:
        return
