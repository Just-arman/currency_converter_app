from unittest.mock import AsyncMock, patch


class TestRunManualParser:
    """Тесты для POST /currency/parser/ — ручной запуск парсера."""

    async def test_successful_run_parser(self, async_client, override_admin):
        """Админ успешно запускает парсер — 200."""
        with patch("app.currency.router.launch_sync_currencies", new_callable=AsyncMock):
            response = await async_client.post("/currency/parser/")
            assert response.status_code == 200
            assert response.json()["message"] == "Парсер запущен вручную"

    async def test_forbidden_for_regular_user(self, async_client, override_user):
        """Проверка на то, что обычный пользователь не имеет доступа — 403."""
        response = await async_client.post("/currency/parser/")
        assert response.status_code == 403