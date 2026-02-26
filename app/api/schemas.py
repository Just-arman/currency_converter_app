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