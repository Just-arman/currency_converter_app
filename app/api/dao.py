from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import update
from typing import List, Tuple
from pydantic import BaseModel
from app.api.schemas import BestRateResponse
from app.config import settings
from app.logger import log
from app.api.models import CurrencyRate
from app.dao.base import BaseDAO


class CurrencyRateDAO(BaseDAO):
    model = CurrencyRate

    @classmethod
    async def bulk_update_currency(cls, session: AsyncSession, records: List[BaseModel]) -> int:
        """Массовое обновление валютных курсов."""
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
        """Находит лучший курс для указанной валюты и операции."""
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
        """Находим лучший курс покупки для указанной валюты."""
        return await cls._find_best_rate(currency_type, 'buy', session)

    @classmethod
    async def find_best_sale_rate(cls, currency_type: str, session: AsyncSession) -> BestRateResponse | None:
        """Находим лучший курс продажи для указанной валюты."""
        return await cls._find_best_rate(currency_type, 'sell', session)