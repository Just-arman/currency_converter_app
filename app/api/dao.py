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
            # log.debug(f"Содержимое records: {records}")
            bank_en_counts = Counter(record.model_dump().get("bank_en") for record in records)
            log.debug(f"Содержимое bank_en_counts: {bank_en_counts}")

            bank_en_counts_items = bank_en_counts.items()
            log.debug(f"Содержимое bank_en_counts_items: {bank_en_counts_items}")

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
                    log.warning(f"Пропуск записи из-за отсутствия bank_en. Данные: {record_dict}")
                    continue

                parsed_records.append(record_dict)
                parsed_bank_ens.add(bank_en)

            # 2. Получаем банки из БД
            result_en = await session.execute(select(cls.model.bank_en))
            result_name = await session.execute(select(cls.model.bank_name))
            db_bank_ens = set(result_en.scalars().all())
            db_bank_names = set(result_name.scalars().all())

            # 3. Определяем разницу
            to_add = {
                r["bank_en"] for r in parsed_records
                if r["bank_en"] not in db_bank_ens and r["bank_name"] not in db_bank_names
            }
            to_delete = db_bank_ens - parsed_bank_ens
            to_update = parsed_bank_ens & db_bank_ens

            counted_banks = 0 # количество банков без дублирований

            # 4. DELETE (удаляем лишние в БД)
            if to_delete:
                delete_stmt = delete(cls.model).where(cls.model.bank_en.in_(to_delete))
                result_del = await session.execute(delete_stmt)
                log.info(f"Удалено банков: {result_del.rowcount}")

            # 5. INSERT (добавляем новые)
            new_records = [r for r in parsed_records if r["bank_en"] in to_add]

            if new_records:
                await session.execute(insert(cls.model), new_records)
                log.info(f"Добавлено банков: {len(new_records)}")
                counted_banks += len(new_records)

            # 6. UPDATE (обновляем существующие)
            # создаём пустое множество для отслеживания уже обновлённых банков
            updated_banks = set()
            for record_dict in parsed_records:
                bank_en = record_dict["bank_en"]

                if bank_en not in to_update:
                    continue
                
                # исключаем bank_en, потому что он связывает данные парсера с записями в бд, его обновлять не нужно
                update_data = {k: v for k, v in record_dict.items() if k != "bank_en"}
                # log.debug(f"Содержимое update_data: {update_data}")

                stmt = update(cls.model).where(cls.model.bank_en == bank_en).values(**update_data)
                result = await session.execute(stmt)
                if result.rowcount > 0 and bank_en not in updated_banks:
                    counted_banks += 1
                    updated_banks.add(bank_en)

            # 7. COMMI (фиксируем результат синхронизации)
            await session.commit()

            # Подсчет количества банков в бд через функцию с прямым подсчетом банков в бд
            total = await cls.get_total_count(session)
            if total == counted_banks:
                log.info("Результаты подсчетов банков одинаковы. ")
            else:
                log.warning("Результаты подсчетов банков отличаются. Требуется проверка. ")

            log.info(
                f"Синхронизация завершена. "
                f"Итоговое количество банков = {counted_banks}. "
            )
            # Значения total и counted_banks должны быть одинаковыми. Исключение: если в бд уже были дублирующиеся банки.

            return counted_banks

        except SQLAlchemyError as e:
            await session.rollback()
            log.error(f"Ошибка синхронизации валют: {e}")
            raise


    @classmethod
    async def find_best_buy_rates(
            cls,
            session: AsyncSession,
            usd: bool = False,
            eur: bool = False,
            count: int = 10,
    ) -> dict[str, List]:
        """Получает лучшие курсы покупки валюты клиентом."""
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
            log.debug(f"Содержимое result функции find_best_buy_rates: {result}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении лучших курсов покупки: {e}")
            raise


    @classmethod
    async def find_best_sell_rates(
            cls,
            session: AsyncSession,
            usd: bool = False,
            eur: bool = False,
            count: int = 10
    ) -> dict[str, List]:
        """Получает лучшие курсы продажи валюты клиентом."""
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
            logger.error(f"Ошибка при получении лучших курсов продажи валюты: {e}")
            raise

    
    @classmethod
    async def get_total_count(cls, session: AsyncSession) -> int:
        """Возвращает количество банков в БД."""
        query = select(func.count(cls.model.id))
        result = await session.execute(query)
        return result.scalar()