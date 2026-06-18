from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import CurrencyRateDAO
from app.api.schemas import (
    CurrencyRateSchema,
    AdminCurrencyRateSchema,
    BankEnSchema,
    BestRatesResponse,
    EurRateSchema,
    UsdRateSchema
)
from app.users.dependencies import get_current_admin_user, get_current_user
from app.users.models import User
from app.config import settings
from app.dao.session_maker import SessionDep
from app.logger import log


router_api = APIRouter(prefix='/api', tags=['Api'])


@router_api.get("/all_currency/", summary="Получить информацию о валютных курсах всех банков")
async def get_all_currency(
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> List[CurrencyRateSchema]:
    """Возвращает актуальные курсы валют всех банков."""
    return await CurrencyRateDAO.find_all(session=session, filters=None)


@router_api.get("/all_currency_admin/", summary="Получить подробную информацию о валютных курсах всех банков через роль админа")
async def get_all_currency_admin(
        user_data: User = Depends(get_current_admin_user),
        session: AsyncSession = SessionDep
) -> List[AdminCurrencyRateSchema]:
    """Возвращает расширенную информацию о курсах валют (только для админов)."""
    return await CurrencyRateDAO.find_all(session=session, filters=None)


@router_api.get("/currency_by_bank_en/{bank_en}", summary="Получить информацию о валютных курсах конкретного банка по его англ названию")
async def get_currency_by_bank_en(
        bank_en: str = Path(description="Название банка на английском языке"),
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> CurrencyRateSchema | None:
    """Возвращает курсы валют конкретного банка по его английскому названию."""
    currencies = await CurrencyRateDAO.find_one_or_none(session=session, filters=BankEnSchema(bank_en=bank_en.lower()))
    if not currencies:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["bank_not_found"])
    return currencies


@router_api.get("/best_buy_rates/", summary="Получить топ банков с выгодными курсами для покупки валюты клиентом")
async def get_best_buy_rates(
        usd: bool = False,
        eur: bool = False,
        count: int = Query(10, description="Количество банков с валютными курсами"),
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> BestRatesResponse:
    """Возвращает топ банков с наиболее выгодными курсами для покупки клиентом."""
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну валюту: usd или eur")
        
    # проверка что указанное количество банков не превышает существующее
    total = await CurrencyRateDAO.get_total_count(session=session)
    if count > total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Запрошено количество банков, превышающее доступное количество. "
                f"Следует указать количество, не превышающее: {total}."
            )
        )
    
    raw_result  = await CurrencyRateDAO.find_best_buy_rates(session=session, usd=usd, eur=eur, count=count)
    log.debug(f"{raw_result=}")
    if not raw_result :
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])
    
    # вариант 1
    # result = {}
    # if 'usd' in raw_result:
    #     result['usd'] = [UsdRateSchema.model_validate(r) for r in raw_result['usd']]
    # if 'eur' in raw_result:
    #     result['eur'] = [EurRateSchema.model_validate(r) for r in raw_result['eur']]
    # return result

    # вариант 2
    usd_result = [UsdRateSchema.model_validate(r) for r in raw_result.get('usd', [])]
    eur_result = [EurRateSchema.model_validate(r) for r in raw_result.get('eur', [])]

    res = BestRatesResponse(usd=usd_result, eur=eur_result)
    # log.debug(f"{res=}")
    result = res.model_dump(by_alias=True) # преобразуем объекты схемы в словарь с исп алиасов
    return result


@router_api.get("/best_sell_rates/", summary="Получить топ банков с выгодными курсами для продажи валюты клиентом")
async def get_best_sell_rates(
        usd: bool = False,
        eur: bool = False,
        count: int = Query(10, description="Количество банков с валютными курсами"),
        user_data: User = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> dict[str, List[CurrencyRateSchema]]:
    """Возвращает топ банков с наиболее выгодными курсами для продажи клиентом."""
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну валюту: usd или eur")
    
    # проверка что указанное количество банков не превышает существующее
    total = await CurrencyRateDAO.get_total_count(session=session)
    if count > total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Указанное количество банков превышает доступное количество. "
                f"Следует указать количество меньшее или равное: {total}."
            )
        )

    result = await CurrencyRateDAO.find_best_sell_rates(session=session, usd=usd, eur=eur, count=count)
    if not result:
        raise HTTPException(status_code=404, detail=settings.ERROR_MESSAGES["not_found"])
    return result