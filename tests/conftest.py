import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock
from app.auth.dependencies import get_current_user
from app.main import app


# общие фикстуры для всех тестов

@pytest.fixture(scope="session")
def event_loop():
    """Создаём event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_user():
    """Мок-данные пользователя."""
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


@pytest.fixture
async def async_client():
    """Общие данные асинхронного клиента для тестов."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def override_user(mock_user):
    """Получаем пользователя и затем используем во всех тестах."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    # без lambda
    # def get_mock_user():
    #     return mock_user
    yield
    app.dependency_overrides.clear()