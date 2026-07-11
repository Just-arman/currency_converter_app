from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.currency.router import router_currency
from app.users.router import router_auth, router_users
from app.parser.currency_sync import launch_sync_currencies


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    try:
        await launch_sync_currencies()

        # плановая задача с защитой от дублирования задачи если lifespan вызовется повторно
        scheduler.add_job(
            launch_sync_currencies,
            trigger=IntervalTrigger(minutes=30),
            id="currency_update_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Планировщик запущен")
        yield

    finally:
        if scheduler.running:
            # Остановка планировщика при завершении работы приложения
            scheduler.shutdown()
            logger.info("Планировщик остановлен")


def register_routers(app: FastAPI) -> None:
    """Регистрация роутеров приложения."""

    router_root = APIRouter(tags=["Root"]) # Корневой роутер

    @router_root.get("/")
    def home_page():
        return { "message": "Добро пожаловать!"}

    # Подключение роутеров
    app.include_router(router_root)
    app.include_router(router_auth)
    app.include_router(router_users)
    app.include_router(router_currency)


def create_app() -> FastAPI:
    """
   Создание приложения с конфигурацией FastAPI.
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
    register_routers(app)

    return app


# Создание экземпляра приложения
app = create_app()

