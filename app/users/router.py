from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.auth import authenticate_user, set_tokens
from app.users.dao import RolesDAO, UsersDAO
from app.users.dependencies import (
    check_refresh_token, 
    get_current_admin_user,
    get_current_user,
    get_current_user_for_logout
)
from app.users.models import Users
from app.users.schemas import (
    SAuthResponse,
    SUserRoleUpdate,
    SRoleUpdateByID,
    SUserAddDB,
    SUserAuth,
    SUserRoleRead,
    SUserRegister
)
from app.users.auth import get_password_hash
from app.dao.session_maker import SessionDep, SessionDepCommit
from app.exceptions import (
    IncorrectEmailOrPasswordException, 
    UserNotFoundByIDException, 
    UserAlreadyExistsException
)
from app.logger import log


router_auth = APIRouter(prefix='/auth', tags=['Auth'])
router_users = APIRouter(prefix='/users', tags=['Users'])


@router_auth.post("/register/")
async def register_user(user_data: SUserRegister,
                        session: AsyncSession = SessionDepCommit) -> dict:
    # Проверка на то, зарегистрирован ли такой пользователь уже
    user = await UsersDAO.find_one_or_none(session=session, email=user_data.email)
    if user:
        raise UserAlreadyExistsException

    # Подготовка данных для добавления
    user_data_dict = user_data.model_dump()
    del user_data_dict['confirm_password']   # удаляем повторный пароль, т.к. в БД это поле не нужно

    # Хэширование пароля
    user_data_dict['password'] = get_password_hash(user_data_dict['password'])
    
    # Добавление пользователя
    await UsersDAO.add(session=session, values=SUserAddDB(**user_data_dict))
    return {'message': 'Вы успешно зарегистрированы!'}


@router_auth.post("/login/")
async def login_user(
    response: Response, 
    user_data: SUserAuth, 
    session: AsyncSession = SessionDep
) -> SAuthResponse:
    user = await UsersDAO.find_one_or_none(session=session, email=user_data.email)
    auth_user = await authenticate_user(user=user, password=user_data.password)
    if not auth_user:
        raise IncorrectEmailOrPasswordException
    set_tokens(response, user.id)
    return SAuthResponse(
        ok=True,
        message=f'Авторизация прошла успешно! Здравствуйте, {auth_user.first_name}'
    )


@router_auth.post("/refresh")
async def process_refresh_token(
    response: Response,
    user: Users = Depends(check_refresh_token)
):
    set_tokens(response, user.id)
    return {"message": "Токен успешно обновлен"}


@router_auth.post("/logout")
async def logout(response: Response, user_data: Users = Depends(get_current_user_for_logout)):
    response.delete_cookie("user_access_token")
    response.delete_cookie("user_refresh_token")
    return {'message': 'Пользователь успешно вышел из системы'}


@router_users.get("/me/")
async def get_me(user_data: Users = Depends(get_current_user)) -> SUserRoleRead:
    return user_data


@router_users.get("/all_users/")
async def get_all_users(
    user_data: Users = Depends(get_current_admin_user),
    session: AsyncSession = SessionDep
) -> list[SUserRoleRead]:
    return await UsersDAO.find_all(session=session)


@router_users.patch("/{user_id}/role", summary="Изменить роль пользователя. Вправе только админы.")
async def update_user_role(
    user_id: int = Path(gt=0),
    role_data: SUserRoleUpdate = ...,
    user_data: Users = Depends(get_current_admin_user),
    # user_data: Users = Depends(get_current_user),
    session: AsyncSession = SessionDepCommit,
):
    """
    Меняет роль пользователя по названию роль. 
    """
    # 1. Получаем роль по name
    # if role_data.name is not None: здесь эта проверка не выполняется,
    # поскольку проверка и фильтрация пустых и приравненных к ним значений
    # у нас обработано валидатором в схеме SUserRoleUpdate
    role = await RolesDAO.find_one_or_none(session=session, name=role_data.name)
    if not role:
        raise HTTPException(status_code=404, detail="Роль с таким названием не найдена")

    # 2. Получаем пользователя
    user = await UsersDAO.find_one_or_none(session=session, id=user_id)
    if not user:
        raise UserNotFoundByIDException

    # 3. Проверка на то, есть ли уже у пользователя роль, которую хотим присвоить
    if user.role_id == role.id:
        return {"message": "Пользователь уже имеет данную роль"}

    # 4. Обновляем роль
    values = SRoleUpdateByID(role_id=role.id)
    await UsersDAO.update(session=session, values=values, id=user_id)
    return {"message": f"Роль пользователя обновлена на {role.name}"}


@router_users.delete("/{user_id}", summary="Удалить пользователя по id")
async def delete_user(
    user_id: int = Path(gt=0), 
    user_data: Users = Depends(get_current_admin_user), 
    session: AsyncSession = SessionDepCommit
):
    deleted_count = await UsersDAO.delete(session=session, id=user_id)
    if deleted_count == 0:
        raise UserNotFoundByIDException
    return {'message': 'Пользователь успешно удалён'}
