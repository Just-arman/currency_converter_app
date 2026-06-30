from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.dao import UsersDAO
from app.users.models import Users
from app.config import settings
from app.dao.session_maker import SessionDep
from app.exceptions import (
    ForbiddenException, 
    NoJwtException,
    UserNotFoundByIDException, 
    TokenExpiredException,
    TokenNoFound
)
from app.logger import log


def get_access_token(request: Request) -> str:
    """Извлекаем access_token из кук."""
    token = request.cookies.get("user_access_token")
    if not token:
        raise TokenNoFound
    return token


def get_refresh_token(request: Request) -> str:
    """Извлекаем refresh_token из кук."""
    token = request.cookies.get("user_refresh_token")
    if not token:
        raise TokenNoFound
    return token


async def check_refresh_token(
        token: str = Depends(get_refresh_token),
        session: AsyncSession = SessionDep
) -> Users:
    """ Проверяем refresh_token и возвращаем пользователя."""
    try:
        decoded_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = decoded_payload.get("sub")
        if not user_id:
            raise NoJwtException

        user = await UsersDAO.find_one_or_none(session=session, id=int(user_id))
        if not user:
            raise NoJwtException

        return user
    except JWTError:
        raise NoJwtException


async def get_current_user(token: str = Depends(get_access_token), session: AsyncSession = SessionDep):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.ALGORITHM)
    except JWTError:
        raise NoJwtException

    # получаем expire - время действия токена в секундах
    expire = payload.get("exp")
    # log.info(f"{expire=}")

    # получаем expire_time - время завершения действия токена 
    expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)
    # log.info(f"{expire_time=}")

    # получаем текущее время
    time_now = datetime.now(timezone.utc)
    # log.info(f"{time_now=}")
    if not expire or expire_time < time_now:                 
        raise TokenExpiredException                                           
    
    user_id = payload.get("sub")
    if not user_id:
        raise UserNotFoundByIDException

    user = await UsersDAO.find_one_or_none(session=session, id=int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_admin_user(current_user: Users = Depends(get_current_user)):
    if current_user.role.id in [3, 4]:
        log.debug(f"{current_user=}")
        return current_user
    raise ForbiddenException