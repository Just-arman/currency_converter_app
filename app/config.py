import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    # BOT_TOKEN: str
    # CHAT_ID: int
    SECRET_KEY: str
    ALGORITHM: str
    VALID_CURRENCIES: list = ["usd", "eur"]
    ERROR_MESSAGES: dict = {
        "currency_type": "Некорректный тип валюты. Используйте 'usd' или 'eur'.",
        "range": "Неверно задан диапазон.",
        "not_found": "Не найдены курсы валют.",
        "bank_not_found": "Банк не найден."
    }
    CURRENCY_FIELDS: dict = {
        'usd': {'buy': 'usd_buy', 'sell': 'usd_sell'},
        'eur': {'buy': 'eur_buy', 'sell': 'eur_sell'}
    }
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # SQLITE_PATH: str = "data/db.sqlite3" # раскомментировать, если используем sqlite3
    SQLITE_PATH: str | None = None 

    model_config = SettingsConfigDict(env_file=f"{BASE_DIR}/.env")

    @property
    def DB_URL(self) -> str:
        if self.SQLITE_PATH:
            return f"sqlite+aiosqlite:///{self.BASE_DIR}/{self.SQLITE_PATH}"
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
database_url = settings.DB_URL
