from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.data_parser.scheduler import add_data_to_db, upd_data_to_db
from app.auth.router import router as router_auth


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
        # проверка перед остановкой для защиты от ошибки если планировщик не успел запуститься
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Планировщик остановлен")


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

