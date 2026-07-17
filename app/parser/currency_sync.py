from app.currency.dao import CurrencyRatesDAO
from app.dao.session_maker import session_manager
from app.parser.parser import fetch_all_currencies
from app.logger import log


# Декоратор для парсинга и синхронизации данных в бд
@session_manager.connection(commit=True)
async def launch_sync_currencies(session):
    records = await fetch_all_currencies()
    await CurrencyRatesDAO.bulk_update_data_currency(session=session, records=records)