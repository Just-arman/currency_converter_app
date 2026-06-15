import pytest
from unittest.mock import AsyncMock, patch
from app.api.schemas import CurrencyRateSchema


# фикстуры для тестов api
@pytest.fixture
def currency_rate_data():
    """Тестовые данные для курса валют."""
    return {
        "link": "https://ru.myfin.by/bank/sberbank/currency",
        "bank_en": "sberbank",
        "bank_name": "СберБанк",
        "usd_buy": 74.3,
        "usd_sell": 78.4,
        "eur_buy": 87.7,
        "eur_sell": 93.1,
        "update_time": "26.02.2026 19:04"
    }


@pytest.fixture
def currency_rate_schema(currency_rate_data):
    """Схема для курса валют."""
    return CurrencyRateSchema(**currency_rate_data)


class BaseTestAPI:
    """Базовый класс с общими вспомогательными методами для тестов валютных курсов."""
    async def _test_count_exceeds_total(self, async_client, override_user, url):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total:
            mock_total.return_value = 60
            response = await async_client.get(url)
            assert response.status_code == 400

    async def _test_no_currency_specified(self, async_client, override_user, url):
        response = await async_client.get(url)
        assert response.status_code == 400


# тесты для роутеров api
class TestGetAllCurrency:

    async def test_returns_list_of_currencies(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.find_all", new_callable=AsyncMock) as mock_find_all:
            mock_find_all.return_value = [currency_rate_schema]
            response = await async_client.get("/api/all_currency/")

            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestGetCurrencyByBank:

    async def test_bank_found(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = currency_rate_schema
            response = await async_client.get("/api/currency_by_bank/sberbank")

            assert response.status_code == 200

    async def test_bank_not_found(self, async_client, override_user):
        with patch("app.api.router.CurrencyRateDAO.find_one_or_none", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = None
            response = await async_client.get("/api/currency_by_bank/unknown_bank")

            assert response.status_code == 404


class TestGetBestBuyRate:

    async def test_valid_currency(self, async_client, override_user, best_rate_response):
        with patch("app.api.router.CurrencyRateDAO.find_best_buy_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = best_rate_response
            response = await async_client.get("/api/best_buy_rate/usd")

            assert response.status_code == 200
            assert "rate" in response.json()
            assert "banks" in response.json()
            assert len(response.json()["banks"]) > 1
            
    async def test_invalid_currency(self, async_client, override_user):
            response = await async_client.get("/api/best_buy_rate/gbp")
            assert response.status_code == 400

    async def test_no_rates_found(self, async_client, override_user):
        with patch("app.api.router.CurrencyRateDAO.find_best_buy_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = None
            response = await async_client.get("/api/best_buy_rate/usd")

            assert response.status_code == 404


class TestGetBestBuyRates(BaseTestAPI):

    async def test_no_currency_specified(self, async_client, override_user):
        await self._test_no_currency_specified(async_client, override_user, "/api/best_buy_rates/")

    async def test_count_exceeds_total(self, async_client, override_user):
        await self._test_count_exceeds_total(async_client, override_user, "/api/best_buy_rates/?usd=true&count=100")

    async def test_valid_request_for_buy(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total, \
             patch("app.api.router.CurrencyRateDAO.find_best_buy_rates", new_callable=AsyncMock) as mock_find:
            
            mock_total.return_value = 60
            mock_find.return_value = {"usd": [currency_rate_schema]}
            response = await async_client.get("/api/best_buy_rates/?usd=true")

            assert response.status_code == 200
            assert "usd" in response.json()


class TestGetBestSellRate:

    async def test_valid_currency(self, async_client, override_user, best_rate_response):
        with patch("app.api.router.CurrencyRateDAO.find_best_sell_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = best_rate_response
            response = await async_client.get("/api/best_sell_rate/eur")

            assert response.status_code == 200
        
    async def test_invalid_currency(self, async_client, override_user):
        response = await async_client.get("/api/best_sell_rate/btc")
        assert response.status_code == 400
        
    async def test_no_rates_found(self, async_client, override_user):
        with patch("app.api.router.CurrencyRateDAO.find_best_sell_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = None
            response = await async_client.get("/api/best_sell_rate/eur")

            assert response.status_code == 404


class TestGetBestSellRates(BaseTestAPI):

    async def test_no_currency_specified(self, async_client, override_user):
        await self._test_no_currency_specified(async_client, override_user, "/api/best_buy_rates/")
    
    async def test_count_exceeds_total(self, async_client, override_user):
        await self._test_count_exceeds_total(async_client, override_user, "/api/best_sell_rates/?eur=true&count=100")

    async def test_valid_request_for_sell(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total, \
             patch("app.api.router.CurrencyRateDAO.find_best_sell_rates", new_callable=AsyncMock) as mock_find:

            mock_total.return_value = 60
            mock_find.return_value = {"eur": [currency_rate_schema]}
            response = await async_client.get("/api/best_sell_rates/?eur=true")

            assert response.status_code == 200
            assert "eur" in response.json()
