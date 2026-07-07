import asyncio
from typing import Optional

from aiohttp import ClientError, ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel
from urllib.parse import urlparse, parse_qs, unquote

from app.currency.schemas import CurrencyRateSchema
from app.logger import log


# Асинхронная функция для получения HTML с повторными попытками и экспоненциальной задержкой
async def fetch_html(url: str, session: ClientSession, retries: int = 3) -> Optional[str]:
    attempt = 0
    while attempt < retries:
        try:
            async with session.get(url) as response:
                response.raise_for_status()  # Вызывает исключение при ошибке HTTP
                # log.debug(f"Содержимое response: {response}")
                # log.debug(f"Содержимое response.text(): {response.text()}")
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


# Функция для извлечения информации из ссылки
def get_link_info(link_anchor):
    EXCLUDED_BANK_ENS = {'listing'}
    link_path = link_anchor.get('href') if link_anchor else None
    if link_path:
        # для извлечения банка из нестандартного url
        if 'go?url=' in link_path:
            parsed = urlparse(link_path)
            params = parse_qs(parsed.query)
            inner_url = unquote(params.get('url', [''])[0])  # декодируем внутренний URL
            inner_parsed = urlparse(inner_url)
            inner_params = parse_qs(inner_parsed.query)
            bank_en = inner_params.get('s2', [None])[0]
            log.info(f"Нестандартный URL: {bank_en=}, {inner_url=}")
            if not bank_en or bank_en in EXCLUDED_BANK_ENS:
                return None, None
            url = 'https://ru.myfin.by' + link_path
            return url, bank_en
        parts = link_path.split('/')
        # log.debug(f"{parts=}")
        url = 'https://ru.myfin.by' + link_path
        bank_en = parts[2] if len(parts) > 2 else None
        return url, bank_en
    return None, None


# Функция для парсинга таблицы с валютами
def parse_currency_table(html: str) -> list[BaseModel]:
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
                continue  # Пропускаем этот банк, т.к. курс не удалось извлечь

            # получаем время последнего обновления курса валют конкретного банка.
            update_time = row.find('time').get_text(strip=True)

            # получаем ссылку <a>, именуемую link, для извлечения инфы о банке из неё
            link_info = get_link_info(link)

            # Проверка для того, чтобы исключить рекламные трекеры, где bank_en = None
            if link_info[0] is None or link_info[1] is None:
                continue 

            currencies.append(CurrencyRateSchema(**{
                'bank_name': bank_name, # /СберБанк (link_info[2])
                'bank_en': link_info[1], # /sberbank
                'link': link_info[0], # ''
                'usd_buy': usd_sell,    # зеркально: клиент покупает = банк продаёт
                'usd_sell': usd_buy,    # зеркально: клиент продаёт = банк покупает
                'eur_buy': eur_sell,   
                'eur_sell': eur_buy,   
                'update_time': update_time,
            }))
            # Переменные usd_buy и usd_sell извлекаются из HTML в том виде, как их публикует 
            # сайт (с позиции банка). Но при создании схемы CurrencyRateSchema 
            # значения меняются местами — клиентская перспектива формируется здесь, до записи в БД.

            logger.info(f"{bank_name=}")
        return currencies
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML: {e}")
        return []


# Функция для получения данных с одной страницы
async def fetch_page_data(url: str, session: ClientSession) -> list[BaseModel]:
    html = await fetch_html(url, session)
    if html:
        return parse_currency_table(html)
    return []


# Функция для сбора данных с нескольких страниц асинхронно с обработкой ошибок
async def fetch_all_currencies() -> list[BaseModel]:
    all_currencies = []
    base_url = 'https://ru.myfin.by/currency?page='

    # Создаем сессию с таймаутом
    timeout = ClientTimeout(total=10, connect=5)

    # Добавляем заголовок с агентом, чтобы избежать блокировки автоматических запросов
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 YaBrowser/24.1.0.0"
    }
    async with ClientSession(timeout=timeout, headers=headers) as session:
        tasks = []

        # Обрабатываем первую страницу отдельно, потому что она имеет другой URL
        first_page_url = 'https://ru.myfin.by/currency'
        tasks.append(fetch_page_data(first_page_url, session))

        # Остальные страницы обрабатываем вместе, потому что у них общий URL
        # Создаем задачи для получения данных с нескольких страниц асинхронно
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
        number_page = 1
        for currencies in results:
            log.info(f"Количество банков на странице {number_page}: {len(currencies)}")
            number_page += 1
            all_currencies.extend(currencies)

        # Получаем количество всех спарсенных банков, включая дублирующиеся
        log.info(f"Общее количество полученных банков: {len(all_currencies)}")

    return all_currencies