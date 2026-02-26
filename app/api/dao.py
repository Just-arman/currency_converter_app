from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import update
from typing import List
from pydantic import BaseModel
import logging
from app.api.models import CurrencyRate
from app.dao.base import BaseDAO


logger = logging.getLogger(__name__)

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
                    logger.warning("Пропуск записи: отсутствует bank_en")
                    continue

                update_data = {k: v for k, v in record_dict.items() if k != 'bank_en'}
                if not update_data:
                    logger.warning(f"Пропуск записи: нет данных для обновления банка {bank_en}")
                    continue

                stmt = update(cls.model).where(cls.model.bank_en == bank_en).values(**update_data)
                result = await session.execute(stmt)
                updated_count += result.rowcount

            await session.commit()
            logger.info(f"Обновлено записей: {updated_count}")
            return updated_count
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Ошибка массового обновления: {e}")
            raise