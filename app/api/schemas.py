from datetime import datetime
from pydantic import BaseModel, ConfigDict


class Message(BaseModel):
    text: str


class CurrencyRateSchema(BaseModel):
    link: str
    bank_en: str
    bank_name: str
    usd_buy: float
    usd_sell: float
    eur_buy: float
    eur_sell: float
    update_time: str

    model_config = ConfigDict(from_attributes=True)


class AdminCurrencySchema(CurrencyRateSchema):
    id: int
    created_at: datetime
    updated_at: datetime


class BankNameSchema(BaseModel):
    bank_en: str


class BestRateResponse(BaseModel):
    rate: float
    banks: list[str]