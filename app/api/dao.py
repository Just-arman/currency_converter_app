from collections import Counter
from datetime import datetime, timedelta, timezone

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete, desc, func, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import update

from app.api.models import CurrencyRates
from app.dao.base import BaseDAO
from app.logger import log


class CurrencyRatesDAO(BaseDAO):
    model = CurrencyRates

    # порог: банк помечается неактивным, если не встречался в парсинге дольше этого срока
    MISSING_DURATION_THRESHOLD = timedelta(days=3)
    @classmethod
    async def bulk_update_currency(cls, records: list[BaseModel], session: AsyncSession) -> int:
        """Синхронизация валютных курсов (insert + update + delete) в бд"""
        try:

            # 1. Подготовка данных

            # формируем словарь с использованием класса Counter(), чтобы определить
            # сколько раз каждый банк встречается в парсинге

            records_dict = [record.model_dump(exclude_unset=True) for record in records]

            bank_en_counts = Counter(record.get("bank_en") for record in records_dict)
            duplicates = {k: v for k, v in bank_en_counts.items() if v > 1}
            if duplicates:
                log.warning(f"Дублирующиеся банки с англ названием: {duplicates}")
            
            bank_name_counts = Counter(record.get("bank_name") for record in records_dict)
            duplicate_names = {k: v for k, v in bank_name_counts.items() if v > 1}
            if duplicate_names:
                log.warning(f"Дублирующиеся банки с рус названием: {duplicate_names}")


            parsed_records = []
            parsed_bank_ens = set()
            parsed_bank_names = set()

            for record in records_dict:
                bank_en = record.get("bank_en")
                bank_name = record.get("bank_name")
                
                if not bank_en or not bank_name:
                    log.warning(f"Пропуск записи из-за отсутствия банков. Данные: {record}")
                    continue

                if bank_en in parsed_bank_ens: 
                    log.warning(f"Пропуск дублирующейся записи для {bank_en} в рамках одного прогона")
                    continue
                
                if bank_name in parsed_bank_names:
                    log.warning(f"Пропуск дублирующейся записи для {bank_name} в рамках одного прогона")
                    continue

                parsed_records.append(record)
                parsed_bank_ens.add(bank_en)
                parsed_bank_names.add(bank_name)

            # 2. Получаем банки из БД вместе с их текущим состоянием (is_active, last_seen_at) —
            # это нужно, чтобы дальше определить, кого пометить неактивным, а кого удалить
            result = await session.execute(
                select(
                    cls.model.bank_en,
                    cls.model.bank_name,
                    cls.model.is_active,
                    cls.model.last_seen_at,
                )
            )

            db_banks = {row.bank_en: row for row in result.all()}
            # log.debug(f"{db_banks=}")

            db_bank_ens = {row.bank_en for row in db_banks.values()}
            db_bank_names = {row.bank_name for row in db_banks.values()}

            # 3. Определяем переменные для дальнейшего использования
            to_add = {
                r["bank_en"] for r in parsed_records
                if r["bank_en"] not in db_bank_ens and r["bank_name"] not in db_bank_names
            }
            to_update = parsed_bank_ens & db_bank_ens
            # отсутствующие банки в источнике парсера, но которые есть в бд
            to_missing_now = db_bank_ens - parsed_bank_ens
            datetime_now = datetime.now(timezone.utc)

            # переменная, содержащая дату, с которого началась деактивация банка
            # банк с датой, которая раньше этой, будет удален
            # если равна, то не удаляем
            cutoff = datetime_now - cls.MISSING_DURATION_THRESHOLD

            # банки, которые отсутствуют и ещё были активны
            to_deactivate = {b for b in to_missing_now if db_banks[b].is_active}
            to_delete = {
                b for b in to_missing_now
                if not db_banks[b].is_active
                and db_banks[b].last_seen_at is not None # TODO если поле last_seen_at у банка будет равно None (False), то это будет означать
                and db_banks[b].last_seen_at < cutoff   # только то что данное поле появилось у банков в таблицах, но парсинг не был еще применён?
            }

            counted_banks = 0 # количество банков без дублирований

            # 4. UPDATE (обновляем существующие; отмечаем время обнаружения и реактивируем,
            # если банк ранее был помечен неактивным, но снова появился в парсинге)

            # создаём пустое множество для отслеживания уже обновлённых банков
            updated_banks = set()
            for record_dict in parsed_records:
                bank_en = record_dict["bank_en"]

                if bank_en not in to_update:
                    continue

                # исключаем bank_en, потому что он связывает данные парсера с записями в бд, его обновлять не нужно
                update_data = {k: v for k, v in record_dict.items() if k != "bank_en"}
                update_data["last_seen_at"] = datetime_now
                update_data["is_active"] = True
                # log.debug(f"Содержимое update_data: {update_data}")

                stmt = update(cls.model).where(cls.model.bank_en == bank_en).values(**update_data)
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    updated_banks.add(bank_en)
            log.info(f"Обновлено банков: {len(updated_banks)}")
            counted_banks += len(updated_banks)

            # 5. INSERT (добавляем новые)
            new_records = [r for r in parsed_records if r["bank_en"] in to_add]
            # log.debug(f"{new_records=}")
            # для отображения двух конфликтующих банков при ошибке нарушения уникальности в бд
            # for r in new_records:
            #     log.debug(f"new_record: bank_en={r['bank_en']!r}, bank_name={r['bank_name']!r}")
            if new_records:
                for r in new_records:
                    r["last_seen_at"] = datetime_now
                    r["is_active"] = True
                await session.execute(insert(cls.model), new_records)
            log.info(f"Добавлено банков: {len(new_records)}")
            counted_banks += len(new_records)

            # 6. ДЕАКТИВАЦИЯ + ОТЛОЖЕННОЕ УДАЛЕНИЕ: банки, не встречавшиеся 
            # в парсинге дольше порога, помечаем неактивными вместо удаления 
            # (защита от ложных срабатываний из-за временных сбоев на сайте-источнике)

            # 6a. Банки, которые уже есть в бд, но которых не будет при следующем парсинге — сразу помечаем неактивными
            if to_deactivate:
                deactivate_stmt = (
                    update(cls.model)
                    .where(cls.model.bank_en.in_(to_deactivate))
                    .values(is_active=False)
                )
                result_deactivate = await session.execute(deactivate_stmt)
                if result_deactivate.rowcount > 0:
                    log.info(f"Количество банков, помеченных неактивными: {result_deactivate.rowcount}")
            
            # 6b. Банки, неактивные дольше порога — удаляем из бд
            if to_delete:
                delete_stmt = delete(cls.model).where(cls.model.bank_en.in_(to_delete))
                result_del = await session.execute(delete_stmt)
                if result_del.rowcount > 0:
                    log.info(f"Удалено банков (истёк срок отсрочки): {result_del.rowcount}")

            # 7. COMMIT (фиксируем результат синхронизации)
            await session.commit()

            # Подсчет количества банков в бд через функцию с прямым подсчетом банков в бд
            total = await cls.count_records(session)
            if total == counted_banks:
                log.info("Результаты подсчетов банков одинаковы. ")
            else:
                log.warning("Результаты подсчетов банков отличаются. Требуется проверка. ")

            log.info(
                f"Синхронизация завершена. "
                f"Итоговое количество банков = {counted_banks}. "
            )
            # Значения total и counted_banks должны быть одинаковыми.
            # Исключение: если в бд (total) уже были дублирующиеся банки.
            # либо в бд остаются неактивные банки, у которых ещё не истекла отсрочка —
            # они физически в таблице, но не входят в counted_banks за этот прогон.

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
    ) -> dict[str, list]:
        """Получает лучшие курсы покупки валюты клиентом."""
        result = {}
        try:
            if usd:
                query = select(cls.model).where(cls.model.usd_buy > 0).order_by(cls.model.usd_buy).limit(count)
                res = await session.execute(query)
                result['usd'] = res.scalars().all()
            if eur:
                query = select(cls.model).where(cls.model.eur_buy > 0).order_by(cls.model.eur_buy).limit(count)
                res = await session.execute(query)
                result['eur'] = res.scalars().all()
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
    ) -> dict[str, list]:
        """Получает лучшие курсы продажи валюты клиентом."""
        result = {}
        try:
            if usd:
                query = select(cls.model).where(cls.model.usd_sell > 0).order_by(desc(cls.model.usd_sell)).limit(count)
                res = await session.execute(query)
                result['usd'] = res.scalars().all()
            if eur:
                query = select(cls.model).where(cls.model.eur_sell > 0).order_by(desc(cls.model.eur_sell)).limit(count)
                res = await session.execute(query)
                result['eur'] = res.scalars().all()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении лучших курсов продажи валюты: {e}")
            raise

    @classmethod
    async def count(cls, session: AsyncSession, **filter_by):
        """Подсчитать количество записей."""
        try:
            query = select(func.count(cls.model.id)).filter_by(**filter_by)
            result = await session.execute(query)
            count = result.scalar()
            logger.info(f"Найдено {count} записей.")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при подсчете записей: {e}")
            raise