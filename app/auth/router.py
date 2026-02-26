from typing import List
from fastapi import APIRouter, HTTPException, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.utils import authenticate_user, set_tokens
from app.dependencies.auth_dep import get_current_user, get_current_admin_user, check_refresh_token
from app.dependencies.dao_dep import get_session_with_commit, get_session_without_commit
from app.exceptions import NoUserIdException, UserAlreadyExistsException, IncorrectEmailOrPasswordException
from app.auth.dao import RoleDAO, UsersDAO
from app.auth.schemas import RoleUpdateByID, RoleModelUpdate, SUserAuth, SUserRegister, EmailModel, SUserAddDB, SUserInfo, UserDeleteId, UserID

router = APIRouter()


@router.post("/register/")
async def register_user(user_data: SUserRegister,
                        session: AsyncSession = Depends(get_session_with_commit)) -> dict:
    # Проверка существования пользователя
    user_dao = UsersDAO(session)

    existing_user = await user_dao.find_one_or_none(filters=EmailModel(email=user_data.email))
    if existing_user:
        raise UserAlreadyExistsException

    # Подготовка данных для добавления
    user_data_dict = user_data.model_dump()
    user_data_dict.pop('confirm_password', None)

    # Добавление пользователя
    await user_dao.add(values=SUserAddDB(**user_data_dict))

    return {'message': 'Вы успешно зарегистрированы!'}


@router.post("/login/")
async def auth_user(
        response: Response,
        user_data: SUserAuth,
        session: AsyncSession = Depends(get_session_without_commit)
) -> dict:
    users_dao = UsersDAO(session)
    user = await users_dao.find_one_or_none(
        filters=EmailModel(email=user_data.email)
    )

    if not (user and await authenticate_user(user=user, password=user_data.password)):
        raise IncorrectEmailOrPasswordException
    set_tokens(response, user.id)
    return {
        'ok': True,
        'message': 'Авторизация прошла успешно!'
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("user_access_token")
    response.delete_cookie("user_refresh_token")
    return {'message': 'Пользователь успешно вышел из системы'}


@router.get("/me/")
async def get_me(user_data: User = Depends(get_current_user)) -> SUserInfo:
    return SUserInfo.model_validate(user_data)


@router.get("/all_users/")
async def get_all_users(session: AsyncSession = Depends(get_session_with_commit),
                        user_data: User = Depends(get_current_user),
                        # user_data: User = Depends(get_current_admin_user)
                        ) -> List[SUserInfo]:
    return await UsersDAO(session).find_all()


@router.patch("/{user_id}/role", summary="Обновить роль пользователя")
async def update_user_role(
    user_id: int,
    role_data: RoleModelUpdate,
    session: AsyncSession = Depends(get_session_with_commit),
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
        role = await RoleDAO(session).find_one_or_none(
            RoleModelUpdate(id=role_data.id, name=role_data.name)
        )
        if not role:
            raise HTTPException(
                status_code=400,
                detail="Указанные id и name не соответствуют друг другу",
            )    

    # 3. Если только id
    elif role_data.id is not None:
        role = await RoleDAO(session).find_one_or_none(RoleModelUpdate(id=role_data.id))
        print(f"role=")
        if not role:
            raise HTTPException(status_code=404, detail="Роль с таким id не существует")

    # 4. Если только name
    elif role_data.name is not None:
        role = await RoleDAO(session).find_one_or_none(RoleModelUpdate(name=role_data.name))
        print(f"role=")
        if not role:
            raise HTTPException(status_code=404, detail="Роль с таким названием не найдена")

    # 5. Получаем пользователя
    user_filter = UserID(id=user_id)
    user = await UsersDAO(session).find_one_or_none(user_filter)
    if not user:
        raise NoUserIdException

    # 6. Проверка на ту же роль
    if user.role_id == role.id:
        return {"message": "Данный пользователь уже имеет указанную роль"}

    # 7. Обновляем
    values = RoleUpdateByID(role_id=role.id)
    await UsersDAO(session).update(user_filter, values)
    return {"message": f"Роль пользователя обновлена на {role.name}"}


@router.delete(
    "/{user_id}",
    summary="Удалить пользователя по id"
)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session_with_commit),
):
    filters = UserDeleteId(id=user_id)
    deleted_count = await UsersDAO(session).delete(filters)

    if deleted_count == 0:
        raise NoUserIdException
    return {'message': 'Пользователь успешно удалён'}


@router.post("/refresh")
async def process_refresh_token(
        response: Response,
        user: User = Depends(check_refresh_token)
):
    set_tokens(response, user.id)
    return {"message": "Токены успешно обновлены"}
