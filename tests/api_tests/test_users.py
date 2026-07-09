from unittest.mock import AsyncMock, patch
from app.users.dependencies import check_refresh_token
from app.main import app


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

    async def test_successful_logout(self, async_client, override_user):
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

    async def test_returns_list_of_users(self, async_client, override_admin, mock_user):
        with patch("app.users.router.UsersDAO.find_all", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [mock_user]
            response = await async_client.get("/users/all_users/")
            print(f"{[mock_user]=}")
            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestUpdateUserRole:
    """Тесты для обновления роли пользователя."""

    async def test_successful_role_update(self, async_client, override_admin, mock_user, mock_user_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user, \
             patch("app.users.router.UsersDAO.update", new_callable=AsyncMock):
            mock_find_role.return_value = mock_user_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = 1
            response = await async_client.patch("/users/1/role", json={"name": "User"})
            assert response.status_code == 200

    async def test_user_not_found(self, async_client, override_admin, mock_user_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_user_role
            mock_find_user.return_value = None
            response = await async_client.patch("/users/1/role", json={"name": "User"})
            assert response.status_code == 404

    async def test_same_role(self, async_client, mock_user, override_admin, mock_user_role):
        with patch("app.users.router.RolesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_role, \
             patch("app.users.router.UsersDAO.find_one_or_none", new_callable=AsyncMock) as mock_find_user:
            mock_find_role.return_value = mock_user_role
            mock_find_user.return_value = mock_user
            mock_user.role_id = mock_user_role.id
            response = await async_client.patch("/users/1/role", json={"name": "User"})
            assert response.status_code == 200
            assert "уже имеет" in response.json()["message"]


class TestDeleteUser:
    """Тесты для удаления пользователя."""

    async def test_successful_deletion(self, async_client, override_admin):
        with patch("app.users.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 1
            response = await async_client.delete("/users/1")
            assert response.status_code == 200

    async def test_user_not_found(self, async_client, override_admin):
        with patch("app.users.router.UsersDAO.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = 0
            response = await async_client.delete("/users/999")
            assert response.status_code == 404
