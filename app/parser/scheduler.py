from app.api.dao import CurrencyRateDAO
from app.dao.session_maker import session_manager
from app.parser.parser import fetch_all_currencies
from app.logger import log


# Декоратор для добавления и обновления данных
@session_manager.connection(commit=True)
async def add_or_update_data_to_db(session):
    records = await fetch_all_currencies()
    # log.info(f"Парсер вернул банков: {len(records)}")
    await CurrencyRateDAO.bulk_update_currency(session=session, records=records)