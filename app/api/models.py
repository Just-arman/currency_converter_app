from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.dao.database import Base, float_col, str_uniq


class CurrencyRates(Base):
    __tablename__ = "currencyrates"
    
    bank_name: Mapped[str_uniq] # Название банка (на русском)
    bank_en: Mapped[str_uniq] # Название банка (на английском)
    link: Mapped[str_uniq] # Ссылка на страницу с курсами валют

    # Курсы USD с позиции КЛИЕНТА
    # на сайте банков эти значения указаны в обратном порядке
    usd_buy: Mapped[float_col]      # клиент покупает = банк продаёт
    usd_sell: Mapped[float_col]     # клиент продаёт = банк покупает

    # Курсы EUR с позиции КЛИЕНТА
    eur_buy: Mapped[float_col]
    eur_sell: Mapped[float_col]

    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)) # время последнего обнаружения банка на сайте источнике
    is_active: Mapped[bool] = mapped_column(default=True)   # установка флажка в бд для отсутствующих банков в источнике,
                                                            # данные с таким флажком скрыты из обычных запросов.

    update_time: Mapped[str] # Время последнего обновления
    
    def __repr__(self):
        return f"{self.__class__.__name__}(bank_name={self.bank_name})"
