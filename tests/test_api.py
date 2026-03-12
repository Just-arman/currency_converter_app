import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.api.schemas import BestRateResponse, CurrencyRateSchema
from app.api.utils import validate_currency_type
from app.auth.dependencies import get_current_user
from app.main import app


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


@pytest.fixture
def best_rate_response():
    """Схема для лучшего курса."""
    return BestRateResponse(rate=74.3, banks=["СберБанк", "ВТБ"])


@pytest.fixture
def mock_user():
    """Мок-данные пользователя."""
    user = MagicMock()
    user.id = 1
    user.email = "test@test.com"
    user.role = "user"
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


class BaseRatesTest:
    """Базовый класс с общими вспомогательными методами для тестов валютных курсов."""
    async def _test_count_exceeds_total(self, async_client, override_user, url):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total:
            mock_total.return_value = 60
            response = await async_client.get(url)
            assert response.status_code == 400

    async def _test_no_currency_specified(self, async_client, override_user, url):
        response = await async_client.get(url)
        assert response.status_code == 400


# тесты для validate_currency_type из utils.py
class TestValidateCurrencyType:

    def test_valid_usd(self):
        assert validate_currency_type("usd") == "usd"

    def test_uppercase_converts_to_lowercase(self):
        assert validate_currency_type("USD") == "usd"

    def test_valid_eur(self):
        assert validate_currency_type("eur") == "eur"

    def test_uppercase_eur_converts_to_lowercase(self):
        assert validate_currency_type("EUR") == "eur"


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


class TestGetBestPurchaseRate:

    async def test_valid_currency(self, async_client, override_user, best_rate_response):
        with patch("app.api.router.CurrencyRateDAO.find_best_purchase_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = best_rate_response
            response = await async_client.get("/api/best_purchase_rate/usd")

            assert response.status_code == 200
            assert "rate" in response.json()
            assert "banks" in response.json()
            assert len(response.json()["banks"]) > 1
            
    async def test_invalid_currency(self, async_client, override_user):
            response = await async_client.get("/api/best_purchase_rate/gbp")
            assert response.status_code == 400

    async def test_no_rates_found(self, async_client, override_user):
        with patch("app.api.router.CurrencyRateDAO.find_best_purchase_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = None
            response = await async_client.get("/api/best_purchase_rate/usd")

            assert response.status_code == 404


class TestGetBestPurchaseRates(BaseRatesTest):

    async def test_no_currency_specified(self, async_client, override_user):
        await self._test_no_currency_specified(async_client, override_user, "/api/best_purchase_rates/")

    async def test_count_exceeds_total(self, async_client, override_user):
        await self._test_count_exceeds_total(async_client, override_user, "/api/best_purchase_rates/?usd=true&count=100")

    async def test_valid_request_for_purchase(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total, \
             patch("app.api.router.CurrencyRateDAO.find_best_purchase_rates", new_callable=AsyncMock) as mock_find:
            
            mock_total.return_value = 60
            mock_find.return_value = {"usd": [currency_rate_schema]}
            response = await async_client.get("/api/best_purchase_rates/?usd=true")

            assert response.status_code == 200
            assert "usd" in response.json()


class TestGetBestSaleRate:

    async def test_valid_currency(self, async_client, override_user, best_rate_response):
        with patch("app.api.router.CurrencyRateDAO.find_best_sale_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = best_rate_response
            response = await async_client.get("/api/best_sale_rate/eur")

            assert response.status_code == 200
        
    async def test_invalid_currency(self, async_client, override_user):
        response = await async_client.get("/api/best_sale_rate/btc")
        assert response.status_code == 400
        
    async def test_no_rates_found(self, async_client, override_user):
        with patch("app.api.router.CurrencyRateDAO.find_best_sale_rate", new_callable=AsyncMock) as mock_find:

            mock_find.return_value = None
            response = await async_client.get("/api/best_sale_rate/eur")

            assert response.status_code == 404


class TestGetBestSaleRates(BaseRatesTest):

    async def test_no_currency_specified(self, async_client, override_user):
        await self._test_no_currency_specified(async_client, override_user, "/api/best_purchase_rates/")
    
    async def test_count_exceeds_total(self, async_client, override_user):
        await self._test_count_exceeds_total(async_client, override_user, "/api/best_sale_rates/?eur=true&count=100")

    async def test_valid_request_for_sale(self, async_client, override_user, currency_rate_schema):
        with patch("app.api.router.CurrencyRateDAO.get_total_count", new_callable=AsyncMock) as mock_total, \
             patch("app.api.router.CurrencyRateDAO.find_best_sale_rates", new_callable=AsyncMock) as mock_find:

            mock_total.return_value = 60
            mock_find.return_value = {"eur": [currency_rate_schema]}
            response = await async_client.get("/api/best_sale_rates/?eur=true")

            assert response.status_code == 200
            assert "eur" in response.json()
