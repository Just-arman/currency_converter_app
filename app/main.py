from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import asyncio
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.data_parser.scheduler import add_data_to_db
from app.auth.router import router as router_auth


scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация приложения...")
    await add_data_to_db()
    yield
    logger.info("Завершение работы приложения...")


def register_routers(app: FastAPI) -> None:
    """Регистрация роутеров приложения."""
    # Корневой роутер
    root_router = APIRouter()

    @root_router.get("/", tags=["root"])
    def home_page():
        return { "message": "Добро пожаловать!"}

    # Подключение роутеров
    app.include_router(root_router, tags=["root"])
    app.include_router(router_auth, tags=['Auth'], prefix='/auth')


def create_app() -> FastAPI:
    """
   Создание и конфигурация FastAPI приложения.
   Returns:
       Сконфигурированное приложение FastAPI
   """
    app = FastAPI(lifespan=lifespan)

    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Монтирование статических файлов
    app.mount('/static', StaticFiles(directory='app/static'), name='static')
    register_routers(app)

    return app


# Создание экземпляра приложения
app = create_app()

