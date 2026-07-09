from unittest.mock import MagicMock

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.users.dependencies import get_current_user, get_current_admin_user
from app.main import app


# общий event loop
@pytest.fixture(scope="session")
def event_loop():
    """Создаём event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# HTTP-клиент
@pytest.fixture
async def async_client():
    """AsyncClient обеспечивает реальные HTTP-запросы к приложению
    без запуска сервера и без сетевых соединений."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


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


# переопределение dependencies
@pytest.fixture
def override_user(mock_user):
    """Подменяет get_current_user моком обычного пользователя.
    Используется в тестах эндпоинтов, доступных авторизованному пользователю."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    # без lambda
    # def get_mock_user():
    #     return mock_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def override_admin(mock_admin):
    """Подменяет get_current_admin_user моком администратора.
    Используй в тестах эндпоинтов, защищённых правами администратора
    (update_user_role, get_all_users, all_currency_admin и т.п.)."""
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin
    yield
    app.dependency_overrides.clear()