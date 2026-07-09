from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.main import app


@pytest.fixture
def mock_bank():
    """Мок объекта банка с курсами валют.
    Содержит все поля, необходимые для валидации CurrencyRateSchema и AdminCurrencyRateSchema."""
    bank = MagicMock()
    bank.bank_en = "sberbank"
    bank.bank_name = "Сбербанк"
    bank.link = "https://ru.myfin.by/bank/sberbank/currency"
    bank.is_active = True
    bank.usd_buy = 78.5
    bank.usd_sell = 76.2
    bank.eur_buy = 85.3
    bank.eur_sell = 83.1
    bank.update_time = "26.06.2026 19:04"
    bank.id = 1
    bank.created_at = datetime(2026, 1, 1)
    bank.updated_at = datetime(2026, 6, 1)
    return bank


class TestGetAllCurrencyRates:
    """Тесты для GET /currency/all_currency_rates/ — список курсов всех банков."""

    async def test_returns_list_of_currencies(self, async_client, override_user, mock_bank):
        """Авторизованный пользователь получает список банков с курсами."""
        with patch("app.currency.router.CurrencyRatesDAO.find_all", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [mock_bank]
            response = await async_client.get("/currency/all_currency_rates/")
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    async def test_unauthorized_returns_400(self, async_client):
        """Без токена в куках — 400 (токен отсутствует)."""
        response = await async_client.get("/currency/all_currency_rates/")
        assert response.status_code == 400


class TestGetAllCurrencyAdmin:
    """Тесты для GET /currency/all_currency_admin/ — расширенный список только для администратора."""

    async def test_returns_list_for_admin(self, async_client, override_admin, mock_bank):
        """Администратор получает расширенный список банков."""
        with patch("app.currency.router.CurrencyRatesDAO.find_all", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = [mock_bank]
            response = await async_client.get("/currency/all_currency_rates_admin/")
            assert response.status_code == 200

    async def test_forbidden_for_ordinary_user(self, async_client, override_user):
        """Обычный пользователь не имеет доступа — 403."""
        response = await async_client.get("/currency/all_currency_rates_admin/")
        assert response.status_code == 403


class TestGetCurrencyByBankEn:
    """Тесты для GET /currency/currency_rates_by_bank_en/{bank_en} — курсы конкретного банка."""

    async def test_returns_currency_for_active_bank(self, async_client, override_user, mock_bank):
        """Банк найден и активен — возвращается 200 с данными."""
        with patch("app.currency.router.CurrencyRatesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_bank
            response = await async_client.get("/currency/currency_rates_by_bank_en/sberbank")
            assert response.status_code == 200

    async def test_bank_not_found_returns_404(self, async_client, override_user):
        """Банк не найден в БД — 404."""
        with patch("app.currency.router.CurrencyRatesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None
            response = await async_client.get("/currency/currency_rates_by_bank_en/unknown")
            assert response.status_code == 404

    async def test_inactive_bank_returns_503(self, async_client, override_user, mock_bank):
        """Банк найден в БД, но неактивен — 503."""
        mock_bank.is_active = False
        with patch("app.currency.router.CurrencyRatesDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_bank
            response = await async_client.get("/currency/currency_rates_by_bank_en/sberbank")
            assert response.status_code == 503


class TestGetBestRates:
    """Тесты для GET /currency/best_rates/ — топ банков с лучшими курсами."""

    async def test_count_exceeds_total_returns_400(self, async_client, override_user):
        """В запросе указано больше банков, чем есть в БД — 400."""
        with patch("app.currency.router.CurrencyRatesDAO.count_records", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 60
            response = await async_client.get("/currency/best_rates/?buy=true&usd=true&count=100")
            assert response.status_code == 400
    
    async def test_successful_best_rates(self, async_client, override_user):
        """buy=true, usd=true — успешный ответ с данными."""
        with patch("app.currency.router.CurrencyRatesDAO.count_records", new_callable=AsyncMock) as mock_count, \
            patch("app.currency.router.build_operation_rates", new_callable=AsyncMock) as mock_build:
            mock_count.return_value = 60
            mock_build.return_value = MagicMock()
            response = await async_client.get("/currency/best_rates/?buy=true&usd=true&count=10")
            assert response.status_code == 200


class TestConvertRubToForeign:
    """Тесты для GET /currency/convert/{bank_en}/rub-to-foreign — конвертация рублей в валюту."""

    async def test_no_currency_returns_400(self, async_client, override_user):
        """Не выбрана валюта — 400."""
        response = await async_client.get("/currency/convert/sberbank/rub-to-foreign?amount=100")
        assert response.status_code == 400

    async def test_successful_usd_conversion(self, async_client, override_user, mock_bank):
        """Успешная конвертация рублей в USD — 200 с результатом."""
        with patch("app.currency.router.get_bank", new_callable=AsyncMock) as mock_get_bank:
            mock_get_bank.return_value = mock_bank
            response = await async_client.get("/currency/convert/sberbank/rub-to-foreign?amount=100&usd=true")
            assert response.status_code == 200
            data = response.json()
            assert data["amount"] == 100
            assert data["bank_en"] == "sberbank"
            assert data["usd"]
            assert data["eur"] is None


class TestConvertForeignToRub:
    """Тесты для GET /currency/convert/{bank_en}/foreign-to-rub — конвертация валюты в рубли."""

    async def test_no_currency_returns_400(self, async_client, override_user):
        """Не выбрана валюта — 400."""
        response = await async_client.get("/currency/convert/sberbank/foreign-to-rub?amount=100")
        assert response.status_code == 400

    async def test_successful_usd_conversion(self, async_client, override_user, mock_bank):
        """Успешная конвертация USD в рубли — 200 с результатом."""
        with patch("app.currency.router.get_bank", new_callable=AsyncMock) as mock_get_bank:
            mock_get_bank.return_value = mock_bank
            response = await async_client.get("/currency/convert/sberbank/foreign-to-rub?amount=100&usd=true")
            assert response.status_code == 200
            data = response.json()
            assert data["amount"] == 100
            assert data["bank_en"] == "sberbank"
            assert data["usd"]
            assert data["eur"] is None