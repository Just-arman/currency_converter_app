from collections import Counter
from typing import List

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete, desc, func, insert, select
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
        """Синхронизация валютных курсов (insert + update + delete) в бд"""
        try:
            # проверка на дублирующиеся банки
            bank_en_counts = Counter(record.model_dump().get("bank_en") for record in records)
            duplicates = {k: v for k, v in bank_en_counts.items() if v > 1}
            if duplicates:
                log.warning(f"Дублирующиеся банки: {duplicates}")

            # 1. Подготовка данных
            parsed_records = []
            parsed_bank_ens = set()

            for record in records:
                record_dict = record.model_dump(exclude_unset=True)
                bank_en = record_dict.get("bank_en")
                
                if not bank_en:
                    log.warning(f"Пропуск записи: отсутствует bank_en. Данные: {record_dict}")
                    continue

                parsed_records.append(record_dict)
                parsed_bank_ens.add(bank_en)

            # 2. Получаем банки из БД
            result = await session.execute(select(cls.model.bank_en))
            log.debug(f"result = {result}")
            # db_bank_ens_first = result.scalars().all()
            # log.debug(f"db_bank_ens = {db_bank_ens_first}")
            db_bank_ens = set(result.scalars().all())
            log.debug(f"db_bank_ens = {db_bank_ens}")

            # 3. Определяем разницу
            to_add = parsed_bank_ens - db_bank_ens
            to_delete = db_bank_ens - parsed_bank_ens
            to_update = parsed_bank_ens & db_bank_ens

            counted_banks = 0 # количество банков без дублирований

            # 4. DELETE (удаляем лишние в БД)
            if to_delete:
                delete_stmt = delete(cls.model).where(cls.model.bank_en.in_(to_delete))
                result = await session.execute(delete_stmt)
                log.info(f"Удалено банков: {result.rowcount}")

            # 5. INSERT (добавляем новые)
            new_records = [r for r in parsed_records if r["bank_en"] in to_add]

            if new_records:
                await session.execute(insert(cls.model), new_records)
                log.info(f"Добавлено банков: {len(new_records)}")
                counted_banks += len(new_records)

            # 6. UPDATE (обновляем существующие)
            updated_banks = set()
            for record_dict in parsed_records:
                bank_en = record_dict["bank_en"]

                if bank_en not in to_update:
                    continue

                update_data = {k: v for k, v in record_dict.items() if k != "bank_en"}

                if not update_data:
                    continue

                stmt = update(cls.model).where(cls.model.bank_en == bank_en).values(**update_data)
                result = await session.execute(stmt)
                if result.rowcount > 0 and bank_en not in updated_banks:
                    counted_banks += 1
                    updated_banks.add(bank_en)

            # 7. COMMIT
            await session.commit()

            log.info(
                f"Синхронизация завершена: "
                f"Итоговое количество банков = {counted_banks}. "
            )

            return counted_banks

        except SQLAlchemyError as e:
            await session.rollback()
            log.error(f"Ошибка синхронизации валют: {e}")
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