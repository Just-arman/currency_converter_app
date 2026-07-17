from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi.responses import Response
from jose import jwt

from app.config import settings
from app.logger import log


# улучшенный прежний формат создания токена
def create_tokens(data: dict) -> dict:
    now = datetime.now(timezone.utc)

    def _encode(token_type: str, expire: datetime) -> str:  
        # новый формат
        payload = {**data, "exp": int(expire.timestamp()), "type": token_type}
        
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return token

    return {
        "access_token": _encode("access", now + timedelta(hours=3)),
        "refresh_token": _encode("refresh", now + timedelta(hours=24)),
    }


# улучшенный прежний формат установки токена в cookies ответа
def set_tokens(response: Response, user_id: int):
    tokens = create_tokens(data={"sub": str(user_id)})
    cookie_params = {"httponly": True, "secure": True, "samesite": "lax"}

    response.set_cookie(key="user_access_token", value=tokens["access_token"], **cookie_params)
    response.set_cookie(key="user_refresh_token", value=tokens["refresh_token"], **cookie_params)


# Настройка алгоритма bcrypt для безопасного хеширования и проверки паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Хэшируем пароль для сохранения в БД
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Проверяем соответствие введенного пароля его хэшированной форме из БД
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# прежний формат аутентификации пользователя
async def authenticate_user(user, password):
    if not user or not verify_password(plain_password=password, hashed_password=user.password):
        return None
    return user