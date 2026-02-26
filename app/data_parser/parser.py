import asyncio
from loguru import logger
from bs4 import BeautifulSoup
from aiohttp import ClientSession, ClientTimeout, ClientError
from typing import List, Optional
from pydantic import BaseModel
from app.api.schemas import CurrencyRateSchema


# Асинхронная функция для получения HTML с повторными попытками и экспоненциальной задержкой
async def fetch_html(url: str, session: ClientSession, retries: int = 3) -> Optional[str]:
    attempt = 0
    while attempt < retries:
        try:
            async with session.get(url) as response:
                response.raise_for_status()  # Вызывает исключение при ошибке HTTP
                return await response.text()
        except (ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Ошибка при запросе {url}: {e}")
            attempt += 1
            if attempt == retries:
                logger.critical(f"Не удалось получить данные с {url} после {retries} попыток")
                raise
            # Экспоненциальная задержка при попытках парсинга
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"Неизвестная ошибка при запросе {url}: {e}")
            raise


# Функция для извлечения информации о ссылке
def get_link_info(link_anchor):
    link_path = link_anchor.get('href') if link_anchor else None
    if link_path: # '/bank/sberbank/currency'
        parts = link_path.split('/')
        logger.info(f"{parts=}")
        url = 'https://ru.myfin.by' + link_path
        bank_en = parts[2] if len(parts) > 2 else None
        # logger.info(f"{bank_en=}")
        return url, bank_en
    return None, None


# Функция для парсинга таблицы с валютами
def parse_currency_table(html: str) -> List[BaseModel]:
    soup = BeautifulSoup(html, 'html.parser')

    try:
        # Находим таблицу с валютными курсами
        table = soup.find('table', class_='content_table').find('tbody')
        rows = table.find_all('tr')

        currencies = []
        # Извлекаем информацию о каждом банке
        for row in rows:
            bank_name = row.find('td', class_='bank_name').get_text(strip=True)
            link = row.find('a')

            try:
                # Преобразуем курсы валют в float
                usd_buy = float(row.find_all('td', class_='USD')[0].get_text(strip=True).replace(',', '.'))
                usd_sell = float(row.find_all('td', class_='USD')[1].get_text(strip=True).replace(',', '.'))
                eur_buy = float(row.find_all('td', class_='EUR')[0].get_text(strip=True).replace(',', '.'))
                eur_sell = float(row.find_all('td', class_='EUR')[1].get_text(strip=True).replace(',', '.'))
            except (ValueError, IndexError) as e:
                logger.warning(f"Ошибка при парсинге курсов валют для {bank_name}: {e}")
                continue  # Пропускаем этот банк, если курс не удалось извлечь

            update_time = row.find('time').get_text(strip=True)
            link_info = get_link_info(link)
            # Проверка для того, чтобы исключить рекламные трекеры, где bank_en = None
            if link_info[0] is None or link_info[1] is None:
                continue 

            currencies.append(CurrencyRateSchema(**{
                'bank_name': bank_name, # /sberbank (link_info[2])
                # 'bank_name': link_info[2], # /sberbank (link_info[2])
                'bank_en': link_info[1], # /bank
                'link': link_info[0], # ''
                'usd_buy': usd_buy,
                'usd_sell': usd_sell,
                'eur_buy': eur_buy,
                'eur_sell': eur_sell,
                'update_time': update_time,
            }))
        return currencies
    except Exception as e:
        # logger.error(f"Ошибка при парсинге HTML: {e}")
        logger.exception(f"Ошибка при парсинге HTML: {e}")
        return []


# Функция для получения данных с одной страницы
async def fetch_page_data(url: str, session: ClientSession) -> List[BaseModel]:
    html = await fetch_html(url, session)
    if html:
        return parse_currency_table(html)
    return []


# Функция для сбора данных с нескольких страниц асинхронно с обработкой ошибок
async def fetch_all_currencies() -> List[BaseModel]:
    all_currencies = []
    base_url = 'https://ru.myfin.by/currency?page='

    # Создаем сессию с таймаутом
    timeout = ClientTimeout(total=10, connect=5)
    async with ClientSession(timeout=timeout) as session:
        tasks = []

        # Для первой страницы, потому что она имеет другой URL
        tasks.append(fetch_page_data('https://ru.myfin.by/currency', session))

        # Для следующих страниц, потому что у них общий URL
        # Создаем асинхронные задачи для получения данных с нескольких страниц
        for page in range(2, 5):
            url = f'{base_url}{page}'
            tasks.append(fetch_page_data(url, session))

        # Дожидаемся выполнения всех задач
        # Вариант, где все задачи выполняются параллельно
        results = await asyncio.gather(*tasks)

        # Вариант, где все задачи выполняются последовательно
        # results = []
        # for task in tasks:
        #     result = await task  # ждём каждую страницу по очереди
        #     results.append(result)

        # Обрабатываем полученные данные
        for currencies in results:
            all_currencies.extend(currencies)

    return all_currencies