from contextlib import asynccontextmanager
from functools import wraps
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
        Создаёт новую сессию бд и передает её другому коду на работу с ней.
        """
        async with self.session_maker() as session:
            try:
                yield session
            except HTTPException:
                raise
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
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка транзакции: {e}")
            raise
    
    @asynccontextmanager
    async def commit(self, session: AsyncSession) -> AsyncGenerator[None, None]:
        """
        Управление транзакцией: коммит при успехе, откат при ошибке.
        """
        try:
            yield
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
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
        Декоратор для управления сессией вне FastAPI (фоновые задачи, скрипты, шедулеры)
        с возможностью настройки уровня изоляции

        - параметр `isolation_level`: уровень изоляции для транзакции (например, "SERIALIZABLE").
        """
        def decorator(method):
            @wraps(method)
            async def wrapper(*args, **kwargs):
                async with self.create_session() as session:
                    if commit:
                        async with self.transaction(session):
                            return await method(*args, session=session, **kwargs)
                    return await method(*args, session=session, **kwargs)
            return wrapper
        return decorator


# Инициализация менеджера сессий базы данных
session_manager = DatabaseSessionManager(async_session_maker)

# Зависимости FastAPI для использования сессий
# без коммита
SessionDep = Depends(session_manager.get_session_without_transaction)
# с коммитом
SessionDepCommit = Depends(session_manager.get_session_with_transaction)