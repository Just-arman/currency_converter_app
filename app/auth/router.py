from typing import List
from fastapi import APIRouter, HTTPException, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.auth import authenticate_user, set_tokens
from app.dao.session_maker import SessionDep, SessionDepCommit
from app.auth.dependencies import get_current_user, get_current_admin_user, check_refresh_token
from app.exceptions import NoUserIdException, UserAlreadyExistsException, IncorrectEmailOrPasswordException
from app.auth.dao import RoleDAO, UsersDAO
from app.auth.schemas import (
    RoleUpdateByID, RoleModelUpdate, SUserAuth, SUserRegister, 
    EmailModel, SUserAddDB, SUserInfo, UserDeleteId, UserID
)


router = APIRouter(prefix='/auth', tags=['Auth'])


@router.post("/register/")
async def register_user(user_data: SUserRegister,
                        session: AsyncSession = SessionDepCommit) -> dict:
    # Проверка существования пользователя
    user = await UsersDAO.find_one_or_none(session=session, filters=EmailModel(email=user_data.email))
    if user:
        raise UserAlreadyExistsException

    # Подготовка данных для добавления
    user_data_dict = user_data.model_dump()
    del user_data_dict['confirm_password']

    # Добавление пользователя
    await UsersDAO.add(session=session, values=SUserAddDB(**user_data_dict))

    return {'message': 'Вы успешно зарегистрированы!'}


# улучшенный старый формат
@router.post("/login/")
async def login_user(response: Response, user_data: SUserAuth, session: AsyncSession = SessionDep):
    user = await UsersDAO.find_one_or_none(session=session, filters=EmailModel(email=user_data.email))
    auth_user = await authenticate_user(user=user, password=user_data.password)
    if not user and not auth_user:
        raise IncorrectEmailOrPasswordException
    set_tokens(response, user.id)
    return {'ok': True, 'message': 'Авторизация прошла успешно!'}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("user_access_token")
    response.delete_cookie("user_refresh_token")
    return {'message': 'Пользователь успешно вышел из системы'}


@router.get("/me/")
async def get_me(user_data: User = Depends(get_current_user)) -> SUserInfo:
    return SUserInfo.model_validate(user_data)


@router.get("/all_users/")
async def get_all_users(session: AsyncSession = SessionDep,
                        user_data: User = Depends(get_current_user),
                        # user_data: User = Depends(get_current_admin_user)
                        ) -> List[SUserInfo]:
    return await UsersDAO.find_all(session)


@router.patch("/{user_id}/role", summary="Обновить роль пользователя")
async def update_user_role(
    user_id: int,
    role_data: RoleModelUpdate,
    session: AsyncSession = SessionDepCommit,
):
    """
    Меняет роль пользователя по id или name.
    """

    if role_data.name == "string":
        role_data.name = None

    # 1. Проверка: оба поля пустые
    if role_data.id is None and role_data.name is None:
        raise HTTPException(
            status_code=400,
            detail="Нужно указать id или name роли"
        )

    # 2. Если указаны оба — проверяем соответствие
    if role_data.id is not None and role_data.name is not None:
        role = await RoleDAO.find_one_or_none(
            session=session,
            filters=RoleModelUpdate(id=role_data.id, name=role_data.name)
        )
        if not role:
            raise HTTPException(
                status_code=400,
                detail="Указанные id и name не соответствуют друг другу",
            )    

    # 3. Если только id
    elif role_data.id is not None:
        role = await RoleDAO.find_one_or_none(
            session=session,
            filters=RoleModelUpdate(id=role_data.id)
        )
        print(f"role=")
        if not role:
            raise HTTPException(status_code=404, detail="Роль с таким id не существует")

    # 4. Если только name
    elif role_data.name is not None:
        role = await RoleDAO.find_one_or_none(
            session=session,
            filters=RoleModelUpdate(name=role_data.name)
        )
        print(f"role=")
        if not role:
            raise HTTPException(status_code=404, detail="Роль с таким названием не найдена")

    # 5. Получаем пользователя
    user_filter = UserID(id=user_id)
    user = await UsersDAO.find_one_or_none(session, user_filter)
    if not user:
        raise NoUserIdException

    # 6. Проверка на ту же роль
    if user.role_id == role.id:
        return {"message": "Данный пользователь уже имеет указанную роль"}

    # 7. Обновляем
    values = RoleUpdateByID(role_id=role.id)
    await UsersDAO.update(session, user_filter, values)
    return {"message": f"Роль пользователя обновлена на {role.name}"}


@router.delete("/{user_id}", summary="Удалить пользователя по id")
async def delete_user(
    user_id: int,
    session: AsyncSession = SessionDepCommit,
):
    filters = UserDeleteId(id=user_id)
    deleted_count = await UsersDAO.delete(session, filters)

    if deleted_count == 0:
        raise NoUserIdException
    return {'message': 'Пользователь успешно удалён'}


@router.post("/refresh")
async def process_refresh_token(
        response: Response,
        user: User = Depends(check_refresh_token)
):
    set_tokens(response, user.id)
    return {"message": "Токен успешно обновлен"}
