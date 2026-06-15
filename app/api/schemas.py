from datetime import datetime
from pydantic import BaseModel, ConfigDict


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


class UsdRateSchema(BaseModel):
    link: str
    bank_en: str
    bank_name: str
    usd_buy: float
    usd_sell: float
    update_time: str

    model_config = ConfigDict(from_attributes=True)


class EurRateSchema(BaseModel):
    link: str
    bank_en: str
    bank_name: str
    eur_buy: float
    eur_sell: float
    update_time: str

    model_config = ConfigDict(from_attributes=True)


class BestRatesResponse(BaseModel):
    usd: list[UsdRateSchema] | None = None
    eur: list[EurRateSchema] | None = None


class AdminCurrencyRateSchema(CurrencyRateSchema):
    id: int
    created_at: datetime
    updated_at: datetime


class BankEnSchema(BaseModel):
    bank_en: str


class Message(BaseModel):
    text: str