import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.auth.dependencies import check_refresh_token
from app.main import app


# Фикстуры для тестов auth
@pytest.fixture
def user_register_data():
    """Тестовые данные для регистрации пользователя."""
    return {
        "email": "newuser@test.com",
        "password": "password123",
        "confirm_password": "password123",
        "phone_number": "+79001234567",
        "first_name": "Иван",
        "last_name": "Иванов"
    }


@pytest.fixture
def user_auth_data():
    """Тестовые данные для авторизации пользователя."""
    return {
        "email": "test@test.com",
        "password": "password123"
    }


@pytest.fixture
def mock_role():
    """Мок-данные роли."""
    role = MagicMock()
    role.id = 1
    role.name = "user"
    return role


class TestRegisterUser:
    """Тесты для регистрации нового пользователя."""

    async def test_successful_registration(self, async_client, user_register_data):
        with patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.auth.router.UsersDAO.add", new_callable=AsyncMock):
            mock_find.return_value = None
            response = await async_client.post("/auth/register/", json=user_register_data)
            assert response.status_code == 200
            assert response.json()["message"] == "Вы успешно зарегистрированы!"

    async def test_user_already_exists(self, async_client, user_register_data, mock_user):
        with patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user
            response = await async_client.post("/auth/register/", json=user_register_data)
            assert response.status_code == 409


class TestLoginUser:
    """Тесты для входа пользователя в аккаунт."""

    async def test_successful_login(self, async_client, user_auth_data, mock_user):
        with patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.auth.router.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_find.return_value = mock_user
            mock_auth.return_value = mock_user
            response = await async_client.post("/auth/login/", json=user_auth_data)
            assert response.status_code == 200
            assert response.json()["ok"] is True

    async def test_invalid_credentials(self, async_client, user_auth_data):
        with patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find, \
             patch("app.auth.router.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_find.return_value = None
            mock_auth.return_value = None
            response = await async_client.post("/auth/login/", json=user_auth_data)
            assert response.status_code == 400


class TestRefreshToken:
    """Тест для обновления токена пользователя."""

    async def test_successful_refresh(self, async_client, mock_user):
        with patch("app.auth.router.check_refresh_token", return_value=mock_user):
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
        response = await async_client.get("/auth/me/")
        assert response.status_code == 200


class TestGetAllUsers:
    """Тест для получения всех пользователей."""

    async def test_returns_list_of_users(self, async_client, override_user, mock_user):
        with patch("app.auth.router.UsersDAO.find_all", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [mock_user]
            response = await async_client.get("/auth/all_users/")
            print(f"{[mock_user]=}")
            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestUpdateUserRole:
    """Тесты для обновления роли пользователя."""

    async def test_successful_role_update(self, async_client, mock_user, mock_role):
        with patch("app.auth.router.RoleDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user, \
             patch("app.auth.router.UsersDAO.update", new_callable=AsyncMock):
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = 2
            response = await async_client.patch("/auth/1/role", json={"id": 1, "name": "user"})
            assert response.status_code == 200

    async def test_both_fields_empty(self, async_client):
        response = await async_client.patch("/auth/1/role", json={"id": None, "name": "string"})
        assert response.status_code == 400

    async def test_id_and_name_mismatch(self, async_client, mock_role):
        with patch("app.auth.router.RoleDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role:
            mock_find_role.return_value = None
            response = await async_client.patch("/auth/1/role", json={"id": 1, "name": "wrongname"})
            assert response.status_code == 400

    async def test_role_not_found_by_id(self, async_client):
        with patch("app.auth.router.RoleDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role:
            mock_find_role.return_value = None
            response = await async_client.patch("/auth/1/role", json={"id": 5})
            assert response.status_code == 404

    async def test_user_not_found(self, async_client, mock_role):
        with patch("app.auth.router.RoleDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = None
            response = await async_client.patch("/auth/1/role", json={"id": 1})
            assert response.status_code == 404

    async def test_same_role(self, async_client, mock_user, mock_role):
        with patch("app.auth.router.RoleDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.auth.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = mock_role.id
            response = await async_client.patch("/auth/1/role", json={"id": 1})
            assert response.status_code == 200
            assert "уже имеет" in response.json()["message"]


class TestDeleteUser:
    """Тесты для удаления пользователя."""

    async def test_successful_deletion(self, async_client):
        with patch("app.auth.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 1
            response = await async_client.delete("/auth/1")
            assert response.status_code == 200

    async def test_user_not_found(self, async_client):
        with patch("app.auth.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 0
            response = await async_client.delete("/auth/999")
            assert response.status_code == 404
