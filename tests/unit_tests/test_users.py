import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.users.dependencies import check_refresh_token
from app.main import app


# фикстура тестовых данных обычных пользователей
@pytest.fixture
def mock_user():
    """Мок обычного пользователя с ролью 'user'."""
    user = MagicMock()
    user.id = 1
    user.email = "test@test.com"
    user.role = MagicMock()
    user.role.id = 1
    user.role.name = "user"
    user.role_id = 1
    user.phone_number = "+79001234567"
    user.first_name = "Иван"
    user.last_name = "Иванов"
    return user

# фикстура тестовых данных админов
@pytest.fixture
def mock_admin():
    """Мок пользователя с ролью 'admin'. Нужен для эндпоинтов,
    защищённых get_current_admin_user."""
    admin = MagicMock()
    admin.id = 2
    admin.email = "admin@test.com"
    admin.role = MagicMock()
    admin.role.id = 2
    admin.role.name = "admin"
    admin.role_id = 2
    admin.phone_number = "+79005464954"
    admin.first_name = "Админ"
    admin.last_name = "Админов"
    return admin


class TestRegisterUser:
    """Тесты для регистрации нового пользователя."""

    async def test_successful_registration(self, async_client, user_register_data):
        with patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.users.router.UsersDAO.add", new_callable=AsyncMock):
            mock_find.return_value = None
            response = await async_client.post("/auth/register/", json=user_register_data)
            assert response.status_code == 200
            assert response.json()["message"] == "Вы успешно зарегистрированы!"

    async def test_user_already_exists(self, async_client, user_register_data, mock_user):
        with patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user
            response = await async_client.post("/auth/register/", json=user_register_data)
            assert response.status_code == 409


class TestLoginUser:
    """Тесты для входа пользователя в аккаунт."""

    async def test_successful_login(self, async_client, user_auth_data, mock_user):
        with patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.users.router.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_find.return_value = mock_user
            mock_auth.return_value = mock_user
            response = await async_client.post("/auth/login/", json=user_auth_data)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    async def test_invalid_credentials(self, async_client, user_auth_data):
        with patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.users.router.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_find.return_value = None
            mock_auth.return_value = None
            response = await async_client.post("/auth/login/", json=user_auth_data)
            assert response.status_code == 400


class TestRefreshToken:
    """Тест для обновления токена пользователя."""

    async def test_successful_refresh(self, async_client, mock_user):
        with patch("app.users.router.check_refresh_token", return_value=mock_user):
            app.dependency_overrides[check_refresh_token] = lambda: mock_user
            response = await async_client.post("/auth/refresh")
            assert response.status_code == 200
            assert response.json()["message"] == "Токен успешно обновлен"
            app.dependency_overrides.clear()


class TestLogoutUser:
    """Тест для выхода пользователя из аккаунта."""

    async def test_successful_logout(self, async_client):
        response = await async_client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Пользователь успешно вышел из системы"


class TestGetMe:
    """Тест для получения залогиненного пользователя."""

    async def test_returns_current_user(self, async_client, override_user, mock_user):
        response = await async_client.get("/users/me/")
        assert response.status_code == 200


class TestGetAllUsers:
    """Тест для получения всех пользователей."""

    async def test_returns_list_of_users(self, async_client, override_user, mock_user):
        with patch("app.users.router.UsersDAO.find_all", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [mock_user]
            response = await async_client.get("/users/all_users/")
            print(f"{[mock_user]=}")
            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestUpdateUserRole:
    """Тесты для обновления роли пользователя."""

    async def test_successful_role_update(self, async_client, mock_user, mock_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user, \
             patch("app.users.router.UsersDAO.update", new_callable=AsyncMock):
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = 2
            response = await async_client.patch("/users/1/role", json={"name": "user"})
            assert response.status_code == 200

    async def test_both_fields_empty(self, async_client):
        response = await async_client.patch("/users/1/role", json={"id": None, "name": "string"})
        assert response.status_code == 400

    async def test_user_not_found(self, async_client, mock_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = None
            response = await async_client.patch("/users/1/role", json={"id": 1})
            assert response.status_code == 404

    async def test_same_role(self, async_client, mock_user, mock_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = mock_role.id
            response = await async_client.patch("/users/1/role", json={"id": 1})
            assert response.status_code == 200
            assert "уже имеет" in response.json()["message"]


class TestDeleteUser:
    """Тесты для удаления пользователя."""

    async def test_successful_deletion(self, async_client):
        with patch("app.users.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 1
            response = await async_client.delete("/users/1")
            assert response.status_code == 200

    async def test_user_not_found(self, async_client):
        with patch("app.users.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 0
            response = await async_client.delete("/users/999")
            assert response.status_code == 404
