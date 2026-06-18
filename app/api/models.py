from sqlalchemy.orm import Mapped
from app.dao.database import Base, float_col, str_uniq


class CurrencyRate(Base):
    # Название банка (на русском)
    bank_name: Mapped[str_uniq]

    # Название банка (на английском)
    bank_en: Mapped[str_uniq]

    # Ссылка на страницу с курсами валют
    link: Mapped[str_uniq]

    # Курсы USD с точки зрения КЛИЕНТА
    # на сайте банков эти значения указаны в обратном порядке
    usd_buy: Mapped[float_col]      # клиент покупает = банк продаёт
    usd_sell: Mapped[float_col]     # клиент продаёт = банк покупает

    # Курсы EUR с точки зрения КЛИЕНТА
    eur_buy: Mapped[float_col]
    eur_sell: Mapped[float_col]

    # Время последнего обновления
    update_time: Mapped[str]
    
    def __repr__(self):
        return f"{self.__class__.__name__}(bank_name={self.bank_name})"
    
    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"bank_name={self.bank_name}, "
            f"usd_buy={self.usd_buy}, "
            f"usd_sell={self.usd_sell}, "
            f"eur_buy={self.eur_buy}, "
            f"eur_sell={self.eur_sell})"
        )