from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dao import CurrencyRatesDAO
from app.api.schemas import (
    ConversionResultSchema,
    CurrencyRateSchema,
    AdminCurrencyRateSchema,
    OperationRatesSchema,
    ConversionSchema,
)
from app.api.service import build_operation_rates, get_active_bank
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
    return await CurrencyRatesDAO.find_all(session=session)


@router_api.get("/all_currency_admin/", summary="Получить подробную информацию о валютных курсах всех банков через роль админа")
async def get_all_currency_admin(
        user_data: Users = Depends(get_current_admin_user),
        session: AsyncSession = SessionDep
) -> list[AdminCurrencyRateSchema]:
    """Возвращает расширенную информацию о курсах валют (только для админов)."""
    return await CurrencyRatesDAO.find_all(session=session)


@router_api.get("/currency_by_bank_en/{bank_en}", summary="Получить информацию о валютных курсах конкретного банка по его англ названию")
async def get_currency_by_bank_en(
        bank_en: str = Path(description="Название банка на английском языке"),
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> CurrencyRateSchema | None:
    """Возвращает курсы валют конкретного банка по его английскому названию."""
    currencies = await CurrencyRatesDAO.find_one_or_none(session=session, bank_en=bank_en.lower())
    if not currencies or not currencies.is_active:
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

    total = await CurrencyRatesDAO.count_records(session=session)
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


@router_api.get("/convert/{bank_en}/rub-to-foreign", summary="Конвертация рублей в иностранную валюту")
async def convert_rub_to_foreign(
        bank_en: str = Path(description="Название банка на английском"),
        amount: float = Query(gt=0, description="Сумма в рублях"),
        usd: bool = False,
        eur: bool = False,
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> ConversionSchema:
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну валюту: usd или eur")

    bank = await get_active_bank(bank_en, session)

    usd_result = None
    eur_result = None

    if usd:
        if bank.usd_sell == 0:
            raise HTTPException(status_code=400, detail="Курс USD на данный момент недоступен для этого банка. Выберите другой банк")
        usd_result = ConversionResultSchema(
            rate=bank.usd_sell,
            result=round(amount * bank.usd_sell, 2),
        )

    if eur:
        if bank.eur_sell == 0:
            raise HTTPException(status_code=400, detail="Курс EUR на данный момент недоступен для этого банка. Выберите другой банк")
        eur_result = ConversionResultSchema(
            rate=bank.eur_sell,
            result=round(amount * bank.eur_sell, 2),
        )

    return ConversionSchema(
        bank_en=bank.bank_en,
        bank_name=bank.bank_name,
        amount=amount,
        usd=usd_result,
        eur=eur_result,
    )


@router_api.get("/convert/{bank_en}/foreign-to-rub", summary="Конвертация иностранной валюты в рубли")
async def convert_foreign_to_rub(
        bank_en: str = Path(description="Название банка на английском"),
        amount: float = Query(gt=0, description="Сумма в валюте"),
        usd: bool = False,
        eur: bool = False,
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> ConversionSchema:
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одну валюту: usd или eur")

    bank = await get_active_bank(bank_en, session)

    usd_result = None
    eur_result = None

    if usd:
        if bank.usd_sell == 0:
            raise HTTPException(status_code=400, detail="Курс USD на данный момент недоступен для этого банка. Выберите другой банк")
        usd_result = ConversionResultSchema(
            rate=bank.usd_sell,
            result=round(amount * bank.usd_sell, 2),
        )

    if eur:
        if bank.eur_sell == 0:
            raise HTTPException(status_code=400, detail="Курс EUR на данный момент недоступен для этого банка. Выберите другой банк")
        eur_result = ConversionResultSchema(
            rate=bank.eur_sell,
            result=round(amount * bank.eur_sell, 2),
        )

    return ConversionSchema(
        bank_en=bank.bank_en,
        bank_name=bank.bank_name,
        amount=amount,
        usd=usd_result,
        eur=eur_result,
    )