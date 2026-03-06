from typing import List

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import update

from app.api.models import CurrencyRate
from app.api.schemas import BestRateResponse
from app.config import settings
from app.dao.base import BaseDAO
from app.logger import log


class CurrencyRateDAO(BaseDAO):
    model = CurrencyRate


    @classmethod
    async def bulk_update_currency(cls, records: List[BaseModel], session: AsyncSession) -> int:
        """Массовое обновление валютных курсов"""
        try:
            updated_count = 0
            for record in records:
                record_dict = record.model_dump(exclude_unset=True)
                if not (bank_en := record_dict.get('bank_en')):
                    log.warning("Пропуск записи: отсутствует bank_en")
                    continue

                update_data = {k: v for k, v in record_dict.items() if k != 'bank_en'}
                if not update_data:
                    log.warning(f"Пропуск записи: нет данных для обновления банка {bank_en}")
                    continue

                stmt = update(cls.model).where(cls.model.bank_en == bank_en).values(**update_data)
                result = await session.execute(stmt)
                updated_count += result.rowcount

            await session.commit()
            log.info(f"Обновлено записей: {updated_count}")
            return updated_count
        except SQLAlchemyError as e:
            await session.rollback()
            log.error(f"Ошибка массового обновления: {e}")
            raise


    @classmethod
    async def _find_best_rate(
            cls,
            currency_type: str,
            operation: str,
            session: AsyncSession
    ) -> BestRateResponse | None:
        """Находит лучший курс для указанной валюты и операции"""
        try:
            field = settings.CURRENCY_FIELDS[currency_type][operation]
            order_by = desc(field) if operation == 'sell' else field

            query = select(cls.model).order_by(order_by)
            result = await session.execute(query)
            rates = result.scalars().all()

            if not rates:
                return None

            best_value = getattr(rates[0], field)
            best_banks = [
                bank.bank_name for bank in rates
                if getattr(bank, field) == best_value
            ]

            return BestRateResponse(rate=best_value, banks=best_banks)
        except SQLAlchemyError as e:
            log.error(f"Ошибка поиска лучшего курса: {e}")
            raise


    @classmethod
    async def find_best_purchase_rate(cls, currency_type: str, session: AsyncSession) -> BestRateResponse | None:
        """Находит лучший курс покупки для указанной валюты"""
        return await cls._find_best_rate(currency_type, 'buy', session)


    @classmethod
    async def find_best_sale_rate(cls, currency_type: str, session: AsyncSession) -> BestRateResponse | None:
        """Находит лучший курс продажи для указанной валюты"""
        return await cls._find_best_rate(currency_type, 'sell', session)
    

    @classmethod
    async def find_best_purchase_rates(
            cls,
            session: AsyncSession,
            usd: bool = False,
            eur: bool = False,
            count: int = 10,
    ) -> dict[str, List]:
        """Получает лучшие курсы покупки для USD и/или EUR."""
        result = {}
        try:
            if usd:
                query = select(cls.model).order_by(cls.model.usd_buy).limit(count)
                res = await session.execute(query)
                result['usd'] = res.scalars().all()
            if eur:
                query = select(cls.model).order_by(cls.model.eur_buy).limit(count)
                res = await session.execute(query)
                result['eur'] = res.scalars().all()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении лучших курсов покупки: {e}")
            raise


    @classmethod
    async def find_best_sale_rates(
            cls,
            session: AsyncSession,
            usd: bool = False,
            eur: bool = False,
            count: int = 10
    ) -> dict[str, List]:
        """Получает лучшие курсы продажи для USD и/или EUR."""
        result = {}
        try:
            if usd:
                query = select(cls.model).order_by(desc(cls.model.usd_sell)).limit(count)
                res = await session.execute(query)
                result['usd'] = res.scalars().all()
            if eur:
                query = select(cls.model).order_by(desc(cls.model.eur_sell)).limit(count)
                res = await session.execute(query)
                result['eur'] = res.scalars().all()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении лучших курсов продажи: {e}")
            raise

    
    @classmethod
    async def get_total_count(cls, session: AsyncSession) -> int:
        """Возвращает общее количество банков в БД."""
        query = select(func.count(cls.model.id))
        result = await session.execute(query)
        return result.scalar()