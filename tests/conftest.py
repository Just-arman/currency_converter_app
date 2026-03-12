import pytest
import asyncio


# общая фикстура для всех тестов
@pytest.fixture(scope="session")
def event_loop():
    """Создаём event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
