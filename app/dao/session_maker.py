from contextlib import asynccontextmanager
from typing import Callable, Optional, AsyncGenerator
from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import text
from functools import wraps
from app.dao.database import async_session_maker


class DatabaseSessionManager:
    """
    Класс для управления асинхронными сессиями базы данных, 
    включая поддержку транзакций и зависимостей для FastAPI по работе с сессией.
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_maker = session_maker

    @asynccontextmanager
    async def create_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Создаёт и предоставляет новую сессию базы данных.
        Гарантирует закрытие сессии по завершении работы.
        """
        async with self.session_maker() as session:
            try:
                yield session
            except HTTPException:
                raise  # пробрасываем HTTP-исключения без логирования
            except Exception as e:
                logger.error(f"Ошибка при создании сессии базы данных: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def transaction(self, session: AsyncSession) -> AsyncGenerator[None, None]:
        """
        Управление транзакцией: коммит при успехе, откат при ошибке.
        """
        try:
            yield
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка транзакции: {e}")
            raise

    async def get_session_without_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Зависимость для FastAPI, возвращающая сессию без управления транзакцией.
        """
        async with self.create_session() as session:
            yield session

    async def get_session_with_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Зависимость для FastAPI, возвращающая сессию с управлением транзакцией.
        """
        async with self.create_session() as session:
            async with self.transaction(session):
                yield session

    def connection(self, isolation_level: Optional[str] = None, commit: bool = True):
        """
        Декоратор для управления сессией с возможностью настройки уровня изоляции и коммита.

        Параметры:
        - `isolation_level`: уровень изоляции для транзакции (например, "SERIALIZABLE").
        - `commit`: если `True`, выполняется коммит после вызова метода.
        """

        def decorator(method):
            @wraps(method)
            async def wrapper(*args, **kwargs):
                async with self.session_maker() as session:
                    try:
                        if isolation_level:
                            await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))

                        result = await method(*args, session=session, **kwargs)

                        if commit:
                            await session.commit()

                        return result
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Ошибка при выполнении транзакции: {e}")
                        raise
                    finally:
                        await session.close()

            return wrapper

        return decorator

    @property
    def session_dependency_without_commit(self) -> Callable:
        """
            Возвращает зависимость для FastAPI с доступом к сессии без транзакции.
            Используется когда не нужен commit транзакции.
        """
        return Depends(self.get_session_without_transaction)

    @property
    def session_dependency_with_commit(self) -> Callable:
        """
            Возвращает зависимость для FastAPI с доступом к сессии с транзакций.
            Используется когда нужен commit транзакции.
        """
        return Depends(self.get_session_with_transaction)


# Инициализация менеджера сессий базы данных
session_manager = DatabaseSessionManager(async_session_maker)

# Зависимости FastAPI для использования сессий
# без коммита
SessionDep = session_manager.session_dependency_without_commit
# с коммитом
SessionDepCommit = session_manager.session_dependency_with_commit

# Пример использования декоратора
# @session_manager.connection(isolation_level="SERIALIZABLE", commit=True)
# async def example_method(*args, session: AsyncSession, **kwargs):
#     # Логика метода
#     pass


# Пример использования зависимости
# @router.post("/register/")
# async def register_user(user_data: SUserRegister, session: AsyncSession = SessionDepCommit):
#     # Логика эндпоинта
#     pass