from typing import Awaitable, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.schemas import BestRatesResponse, USDSchema, EURSchema


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