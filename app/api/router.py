from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import CurrencyRatesDAO
from app.api.schemas import (
    CurrencyRateSchema,
    AdminCurrencyRateSchema,
    BankEnSchema,
    OperationRatesSchema,
)
from app.api.service import build_operation_rates
from app.users.dependencies import get_current_admin_user, get_current_user
from app.users.models import Users
from app.config import settings
from app.dao.session_maker import SessionDep
from app.logger import log


router_api = APIRouter(prefix='/api', tags=['Api'])


@router_api.get("/all_currency/", summary="Получить информацию о валютных курсах всех банков")
async def get_all_currency(
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> list[CurrencyRateSchema]:
    """Возвращает актуальные курсы валют всех банков."""
    return await CurrencyRatesDAO.find_all(session=session, filters=None)


@router_api.get("/all_currency_admin/", summary="Получить подробную информацию о валютных курсах всех банков через роль админа")
async def get_all_currency_admin(
        user_data: Users = Depends(get_current_admin_user),
        session: AsyncSession = SessionDep
) -> list[AdminCurrencyRateSchema]:
    """Возвращает расширенную информацию о курсах валют (только для админов)."""
    return await CurrencyRatesDAO.find_all(session=session, filters=None)


@router_api.get("/currency_by_bank_en/{bank_en}", summary="Получить информацию о валютных курсах конкретного банка по его англ названию")
async def get_currency_by_bank_en(
        bank_en: str = Path(description="Название банка на английском языке"),
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> CurrencyRateSchema | None:
    """Возвращает курсы валют конкретного банка по его английскому названию."""
    currencies = await CurrencyRatesDAO.find_one_or_none(session=session, filters=BankEnSchema(bank_en=bank_en.lower()))
    if not currencies:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["bank_not_found"])
    return currencies


@router_api.get("/best_rates/", summary="Получить топ банков с лучшими курсами покупки и/или продажи валюты")
async def get_best_rates(
        buy: bool = False,
        sell: bool = False,
        usd: bool = False,
        eur: bool = False,
        count: int = Query(10, description="Количество банков с валютными курсами"),
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> OperationRatesSchema:
    """Возвращает топ банков с наиболее выгодными курсами покупки и/или продажи."""
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну валюту: usd или eur")
    if not buy and not sell:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну операцию: buy или sell")

    total = await CurrencyRatesDAO.get_total_count(session=session)
    if count > total:
        raise HTTPException(
            status_code=400,
            detail=f"Указанное количество банков превышает доступное количество. Следует указать не более: {total}."
        )

    buy_result = await build_operation_rates(CurrencyRatesDAO.find_best_buy_rates, session, usd, eur, count) if buy else None
    sell_result = await build_operation_rates(CurrencyRatesDAO.find_best_sell_rates, session, usd, eur, count) if sell else None

    if buy and buy_result is None:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])
    if sell and sell_result is None:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])

    response = OperationRatesSchema(buy=buy_result, sell=sell_result)
    return response.model_dump(by_alias=True, exclude_none=True)