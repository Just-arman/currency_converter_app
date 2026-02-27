from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.utils import validate_currency_type
from app.dependencies.auth_dep import get_current_user, get_current_admin_user
from app.auth.models import User
from app.config import settings
from app.dao.session_maker import SessionDep
from app.api.dao import CurrencyRateDAO
from app.api.schemas import CurrencyRateSchema, BankNameSchema, AdminCurrencySchema, BestRateResponse


router = APIRouter(prefix='/api', tags=['API'])


@router.get("/all_currency/")
async def get_all_currency(
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> List[CurrencyRateSchema]:
    """Возвращает актуальные курсы валют всех банков."""
    return await CurrencyRateDAO.find_all(session=session, filters=None)


@router.get("/currency_by_bank/{bank_en}")
async def get_currency_by_bank(
        bank_en: str,
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> CurrencyRateSchema | None:
    """Возвращает курсы валют конкретного банка по его английскому названию."""
    currencies = await CurrencyRateDAO.find_one_or_none(session=session, filters=BankNameSchema(bank_en=bank_en))
    if not currencies:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["bank_not_found"])
    return currencies


@router.get("/all_currency_admin/")
async def get_all_currency_admin(
        user_data: User = Depends(get_current_admin_user),
        session: AsyncSession = SessionDep
) -> List[AdminCurrencySchema]:
    """Возвращает расширенную информацию о курсах валют (только для админов)."""
    return await CurrencyRateDAO.find_all(session=session, filters=None)


@router.get("/best_purchase_rate/{currency_type}")
async def get_best_purchase_rate(
        currency_type: str,
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> BestRateResponse:
    """Возвращает информацию о банках с лучшим курсом покупки для выбранной валюты."""
    currency_type = validate_currency_type(currency_type)
    result = await CurrencyRateDAO.find_best_purchase_rate(currency_type=currency_type, session=session)
    if not result or not result.banks:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])
    return result


@router.get("/best_sale_rate/{currency_type}")
async def get_best_sale_rate(
        currency_type: str,
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> BestRateResponse:
    """Возвращает информацию о банках с лучшим курсом продажи для выбранной валюты."""
    currency_type = validate_currency_type(currency_type)
    result = await CurrencyRateDAO.find_best_sale_rate(currency_type=currency_type, session=session)
    if not result or not result.banks:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])
    return result