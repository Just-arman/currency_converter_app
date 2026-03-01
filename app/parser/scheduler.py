from app.api.dao import CurrencyRateDAO
from app.dao.session_maker import session_manager
from app.parser.parser import fetch_all_currencies


# Декоратор для добавления и обновления данных
@session_manager.connection(commit=True)
async def add_data_to_db(session):
    count_rate = await CurrencyRateDAO.count(session)
    rez = await fetch_all_currencies()
    if count_rate == 0:
        await CurrencyRateDAO.add_many(instances=rez)
    else:
        await CurrencyRateDAO.bulk_update_currency(session=session, records=rez)

    
# Декоратор для обновления данных
@session_manager.connection(commit=True)
async def upd_data_to_db(session):
    rez = await fetch_all_currencies()
    await CurrencyRateDAO.bulk_update_currency(session=session, records=rez)
