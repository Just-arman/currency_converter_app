from typing import Generic, Type, TypeVar

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy import func
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .database import Base
from app.logger import log


# Объявляем типовой параметр T с ограничением, что это наследник Base
T = TypeVar("T", bound=Base)


class BaseDAO(Generic[T]):
    model: Type[T]

    # для проверки на отсутствие пустых значений модели в дочерних классах
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.model is None:
            raise ValueError(f"В классе {cls.__name__} должна быть указана модель")

    @classmethod
    async def find_one_or_none(cls, session: AsyncSession, **filter_by):
        """Найти одну запись по фильтрам."""
        try:
            query = select(cls.model).filter_by(**filter_by)
            result = await session.execute(query)
            record = result.scalar_one_or_none()
            return record
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске записи по фильтрам {filter_by}: {e}")
            raise

    @classmethod
    async def find_all(cls, session: AsyncSession, **filter_by):
        """Найти все записи."""
        try:
            query = select(cls.model).filter_by(**filter_by)
            result = await session.execute(query)
            records = result.scalars().all()
            return records
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске всех записей по фильтрам {filter_by}: {e}")
            raise

    @classmethod
    async def add(cls, session: AsyncSession, values: BaseModel):
        """Добавить одну запись."""
        values_dict = values.model_dump()
        new_instance = cls.model(**values_dict)
        session.add(new_instance)
        try:
            await session.flush()
            logger.info(f"Запись {cls.model.__name__} успешно добавлена.")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении записи: {e}")
            raise
        return new_instance

    @classmethod
    async def add_many(cls, session: AsyncSession, instances: list[BaseModel]):
        """Добавить несколько записей."""
        values_list = [item.model_dump() for item in instances]
        new_instances = [cls.model(**values) for values in values_list]
        session.add_all(new_instances)
        try:
            await session.flush()
            logger.info(f"Успешно добавлено {len(new_instances)} записей.")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении нескольких записей: {e}")
            raise
        return new_instances

    @classmethod
    async def update(cls, session: AsyncSession, values: BaseModel, **filter_by):
        """Обновить записи по фильтрам."""
        if not filter_by:
            raise ValueError("Нужен хотя бы один фильтр для обновления.")
        values_dict = values.model_dump(exclude_unset=True)
        query = (
            sqlalchemy_update(cls.model)
            .filter_by(**filter_by)
            .values(**values_dict)
            .execution_options(synchronize_session="fetch")
        )
        try:
            result = await session.execute(query)
            logger.info(f"Обновлено {result.rowcount} записей.")
            return result.rowcount
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении записей: {e}")
            raise

    @classmethod
    async def delete(cls, session: AsyncSession, **filter_by):
        """Удалить записи по фильтру."""
        if not filter_by:
            raise ValueError("Нужен хотя бы один фильтр для удаления.")

        query = sqlalchemy_delete(cls.model).filter_by(**filter_by)
        try:
            result = await session.execute(query)
            logger.info(f"Удалено {result.rowcount} записей.")
            return result.rowcount
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при удалении записей: {e}")
            raise

    @classmethod
    async def count_records(cls, session: AsyncSession, **filter_by):
        """Подсчитать количество записей."""
        try:
            query = select(func.count(cls.model.id)).filter_by(**filter_by)
            result = await session.execute(query)
            count = result.scalar()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при подсчете записей: {e}")
            raise

