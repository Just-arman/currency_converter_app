from typing import Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import CurrencyRateDAO
from app.config import settings


def validate_currency_type(currency_type: str) -> str:
    """Проверяет корректность типа валюты."""
    if currency_type.lower() not in settings.VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail=settings.ERROR_MESSAGES["currency_type"])
    return currency_type.lower()