import redis.asyncio as redis

from app.api.dao import CurrencyRatesDAO
from app.dao.session_maker import session_manager
from app.parser.parser import fetch_all_currencies
from app.logger import log


# Декоратор для добавления и обновления данных
@session_manager.connection(commit=True)
async def launch_sync_currencies(session):
    records = await fetch_all_currencies()
    await CurrencyRatesDAO.bulk_update_currency(session=session, records=records)

