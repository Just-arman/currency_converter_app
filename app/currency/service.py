from typing import Awaitable, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.currency.dao import CurrencyRatesDAO
from app.currency.models import CurrencyRates
from app.currency.schemas import BestRatesResponse, USDSchema, EURSchema
from app.exceptions import BankRateNotFoundException, BankRateIsInactiveException


DaoRatesMethod = Callable[..., Awaitable[dict]]

async def build_operation_rates(
    dao_method: DaoRatesMethod,
    session: AsyncSession,
    usd: bool,
    eur: bool,
    count: int,
) -> BestRatesResponse | None:
    """Вызывает DAO-метод (покупка или продажа) и собирает результат в общую схему."""
    raw_result = await dao_method(session=session, usd=usd, eur=eur, count=count)
    usd_list = raw_result.get('usd', [])
    eur_list = raw_result.get('eur', [])

    if not usd_list and not eur_list:
        logger.warning(f"{dao_method.__name__}: не найдено ни одного банка, удовлетворяющего условию")
        return None

    usd_result = [USDSchema.model_validate(r) for r in usd_list]
    eur_result = [EURSchema.model_validate(r) for r in eur_list]
    return BestRatesResponse(usd=usd_result, eur=eur_result)


async def get_bank(bank_en: str, session: AsyncSession) -> CurrencyRates:
    """Получает конкретный банк с курсами валют."""
    bank = await CurrencyRatesDAO.find_one_or_none(session=session, bank_en=bank_en.lower())
    if not bank:
        raise BankRateNotFoundException
    if not bank.is_active:
        raise BankRateIsInactiveException
    return bank