from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CurrencyRateSchema(BaseModel):
    bank_en: str
    bank_name: str
    link: str
    usd_buy: float
    usd_sell: float
    eur_buy: float
    eur_sell: float
    update_time: str

    model_config = ConfigDict(from_attributes=True)


class AdminCurrencyRateSchema(CurrencyRateSchema):
    id: int
    created_at: datetime
    updated_at: datetime


class CurrencyTypeSchema(BaseModel):
    bank_en: str
    bank_name: str
    link: str
    update_time: str

    model_config = ConfigDict(from_attributes=True)


class USDSchema(CurrencyTypeSchema):
    usd_buy: float
    usd_sell: float


class EURSchema(CurrencyTypeSchema):
    eur_buy: float
    eur_sell: float


class BestRatesResponse(BaseModel):
    usd: list[USDSchema] | None = Field(None, alias='USD') # прописной алиас для лучшей видимости
    eur: list[EURSchema] | None = Field(None, alias='EUR')

    model_config = ConfigDict(populate_by_name=True)


class OperationRatesSchema(BaseModel):
    buy: BestRatesResponse | None = None
    sell: BestRatesResponse | None = None


class Message(BaseModel):
    text: str


class ConversionResultSchema(BaseModel):
    rate: float       # курс, по которому считается конвертация
    result: float     # итоговая сумма после конвертации


class ConversionSchema(BaseModel):
    bank_en: str
    bank_name: str
    amount: float
    usd: ConversionResultSchema | None = None
    eur: ConversionResultSchema | None = None