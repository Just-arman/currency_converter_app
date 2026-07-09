from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.currency.dao import CurrencyRatesDAO
from app.currency.schemas import (
    ConversionResultSchema,
    CurrencyRateSchema,
    AdminCurrencyRateSchema,
    OperationRatesSchema,
    ConversionSchema,
)
from app.currency.service import build_operation_rates, get_bank
from app.parser.currency_sync import launch_sync_currencies
from app.users.dependencies import get_current_admin_user, get_current_user
from app.users.models import Users
from app.config import settings
from app.dao.session_maker import SessionDep
from app.logger import log


router_currency = APIRouter(prefix='/currency', tags=['Currency'])


@router_currency.post("/parser/")
async def run_parser_manually(user_data = Depends(get_current_admin_user)):
    """Запускает парсер вручную с обновлением данных в БД - вправе только админы"""
    await launch_sync_currencies()
    return {"message": "Парсер запущен"}


@router_currency.get("/all_currency_rates/", summary="Получить информацию о валютных курсах всех банков")
async def get_all_currency(
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> list[CurrencyRateSchema]:
    """Возвращает актуальные курсы валют всех банков."""
    return await CurrencyRatesDAO.find_all(session=session)


@router_currency.get("/all_currency_rates_admin/", summary="Получить подробную информацию о валютных курсах всех банков через роль админа")
async def get_all_currency_admin(
        user_data: Users = Depends(get_current_admin_user),
        session: AsyncSession = SessionDep
) -> list[AdminCurrencyRateSchema]:
    """Возвращает расширенную информацию о курсах валют (только для админов)."""
    return await CurrencyRatesDAO.find_all(session=session)


@router_currency.get("/currency_rates_by_bank_en/{bank_en}", summary="Получить информацию о валютных курсах конкретного банка по его англ названию")
async def get_currency_rates_by_bank_en(
        bank_en: str = Path(description="Название банка на английском языке"),
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> CurrencyRateSchema | None:
    """Возвращает курсы валют конкретного банка по его английскому названию."""
    rate = await get_bank(bank_en, session)
    return rate


@router_currency.get("/best_rates/", summary="Получить топ банков с лучшими курсами покупки и/или продажи валюты")
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
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну валюту: usd или eur")
    if not buy and not sell:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну операцию: buy или sell")

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


@router_currency.get("/convert/{bank_en}/rub-to-foreign", summary="Конвертация рублей в иностранную валюту")
async def convert_rub_to_foreign(
        bank_en: str = Path(description="Название банка на английском"),
        amount: float = Query(gt=0, description="Сумма в рублях"),
        usd: bool = False,
        eur: bool = False,
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> ConversionSchema:
    """Конвертирует указанную сумму в рублях в иностранную валюту по курсу покупки выбранного банка.
    Клиент покупает валюту — банк продаёт. Расчёт ведётся по курсу покупки клиентом (usd_buy / eur_buy).
    Можно указать одну или обе валюты одновременно — результат вернётся для каждой.
    """
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну валюту: usd или eur")

    bank = await get_bank(bank_en, session)

    usd_result = None
    eur_result = None

    if usd:
        if bank.usd_buy == 0:
            raise HTTPException(status_code=400, detail="Курс USD на данный момент недоступен для этого банка. Выберите другой банк")
        usd_result = ConversionResultSchema(
            rate=bank.usd_buy ,
            result=round(amount / bank.usd_buy , 2),
        )

    if eur:
        if bank.eur_buy == 0:
            raise HTTPException(status_code=400, detail="Курс EUR на данный момент недоступен для этого банка. Выберите другой банк")
        eur_result = ConversionResultSchema(
            rate=bank.eur_buy,
            result=round(amount / bank.eur_buy, 2),
        )

    return ConversionSchema(
        bank_en=bank.bank_en,
        bank_name=bank.bank_name,
        amount=amount,
        usd=usd_result,
        eur=eur_result,
    )


@router_currency.get("/convert/{bank_en}/foreign-to-rub", summary="Конвертация иностранной валюты в рубли")
async def convert_foreign_to_rub(
        bank_en: str = Path(description="Название банка на английском"),
        amount: float = Query(gt=0, description="Сумма в валюте"),
        usd: bool = False,
        eur: bool = False,
        user_data: Users = Depends(get_current_user),
        session: AsyncSession = SessionDep
) -> ConversionSchema:
    """Конвертирует указанную сумму в иностранной валюте в рубли по курсу продажи выбранного банка.
    Клиент продаёт валюту — банк покупает. Расчёт ведётся по курсу продажи клиентом (usd_sell / eur_sell).
    Можно указать одну или обе валюты одновременно.
    """
    if not usd and not eur:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну валюту: usd или eur")

    bank = await get_bank(bank_en, session)

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