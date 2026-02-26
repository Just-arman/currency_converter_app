from app.api.dao import CurrencyRateDAO
from app.dao.session_maker import session_manager
from app.data_parser.parser import fetch_all_currencies


# Декоратор для первичного добавления данных
@session_manager.connection(commit=True)
async def add_data_to_db(session):
    rez = await fetch_all_currencies()
    dao = CurrencyRateDAO(session)
    await dao.add_many(instances=rez)
