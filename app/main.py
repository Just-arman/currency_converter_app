from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.parser.scheduler import add_data_to_db, upd_data_to_db
from app.auth.router import router as router_auth
from app.api.router import router as router_api


scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    try:
        await add_data_to_db()

        # плановая задача с защитой от дублирования задачи если lifespan вызовется повторно
        scheduler.add_job(
            upd_data_to_db,
            trigger=IntervalTrigger(minutes=10),
            # trigger=IntervalTrigger(seconds=5),
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

    router_root = APIRouter() # Корневой роутер

    @router_root.get("/", tags=["Root"])
    def home_page():
        return { "message": "Добро пожаловать!"}

    # Подключение роутеров
    app.include_router(router_root)
    app.include_router(router_auth)
    app.include_router(router_api)


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

