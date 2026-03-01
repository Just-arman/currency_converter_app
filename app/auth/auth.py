from jose import jwt
from datetime import datetime, timedelta, timezone
from fastapi.responses import Response
from app.config import settings
from app.auth.utils import verify_password

from datetime import datetime, timezone
from jose import jwt
from app.config import settings


# улучшенный прежний формат
def create_tokens(data: dict) -> dict:
    now = datetime.now(timezone.utc)

    def _encode(token_type: str, expire: datetime) -> str:
        payload = data.copy()
        payload.update({"exp": int(expire.timestamp()), "type": token_type})
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return {
        "access_token": _encode("access", now + timedelta(hours=1)),
        "refresh_token": _encode("refresh", now + timedelta(hours=3)),
    }


# улучшенный прежний формат
def set_tokens(response: Response, user_id: int):
    tokens = create_tokens(data={"sub": str(user_id)})
    cookie_params = {"httponly": True, "secure": True, "samesite": "lax"}

    response.set_cookie(key="user_access_token", value=tokens["access_token"], **cookie_params)
    response.set_cookie(key="user_refresh_token", value=tokens["refresh_token"], **cookie_params)


# прежний формат
async def authenticate_user(user, password):
    if not user or verify_password(plain_password=password, hashed_password=user.password) is False:
        return None
    return user