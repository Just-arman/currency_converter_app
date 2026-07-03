import pytest
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock, MagicMock
from aiohttp import ClientError

from app.parser.parser import fetch_html, parse_currency_table, get_link_info


"""
Юнит-тесты для функций парсера (app/parser/parser.py), кроме get_link_info
(для неё тесты в отдельном файле).

parse_currency_table — чистая функция (HTML-строка → список схем),
тестируется без моков и внешних зависимостей.

fetch_html — принимает сессию параметром, поэтому сессия мокается напрямую,
без реального сетевого подключения.

get_link_info — чистая функция (HTML-элемент → кортеж url/bank_en),
тестируется без моков: входные данные создаются через BeautifulSoup
из строк с нужным href, сети нет.
"""


def make_table_html(
    bank_name: str = "СберБанк",
    href: str = "/bank/sberbank/currency",
    usd_buy: str = "74,30",
    usd_sell: str = "78,40",
    eur_buy: str = "87,70",
    eur_sell: str = "93,10",
    update_time: str = "26.06.2026 19:04",
) -> str:
    """Собирает минимальный HTML-фрагмент таблицы с одной строкой банка.
    Используется как фикстура данных во всех тестах parse_currency_table."""
    
    return f"""
    <table class="content_table">
      <tbody>
        <tr>
          <td class="bank_name">{bank_name}</td>
          <td><a href="{href}">ссылка</a></td>
          <td class="USD">{usd_buy}</td>
          <td class="USD">{usd_sell}</td>
          <td class="EUR">{eur_buy}</td>
          <td class="EUR">{eur_sell}</td>
          <td><time>{update_time}</time></td>
        </tr>
      </tbody>
    </table>
    """


class TestParseCurrencyTable:
    """Тесты для parse_currency_table — разбор HTML-таблицы в список схем."""

    def test_valid_row_returns_schema_with_swapped_values(self):
        """Курсы в HTML-таблице указаны с точки зрения БАНКА (что банк
        покупает/продаёт), а в схеме нужны курсы с точки зрения КЛИЕНТА
        (что клиент платит/получает) — поэтому USD[0] и USD[1] меняются
        местами. Это самый вероятный к случайному сбою момент в парсере:
        кто-то поменяет порядок — и курсы покупки/продажи перепутаются
        у всех банков, без единой ошибки в логах.

        HTML USD[0]=74.30 (банк покупает) → usd_sell=74.30 (клиент продаёт)
        HTML USD[1]=78.40 (банк продаёт) → usd_buy=78.40 (клиент покупает)"""

        result = parse_currency_table(make_table_html())

        assert len(result) == 1
        bank = result[0]
        assert bank.bank_name == "СберБанк"
        assert bank.bank_en == "sberbank"
        assert bank.link == "https://ru.myfin.by/bank/sberbank/currency"
        assert bank.usd_buy == 78.40    # HTML USD[1] (клиент покупает) → банк продаёт
        assert bank.usd_sell == 74.30   # HTML USD[0] (клиент продает) → банк покупает
        assert bank.eur_buy == 93.10
        assert bank.eur_sell == 87.70
        assert bank.update_time == "26.06.2026 19:04"

    def test_row_with_invalid_currency_data_is_skipped(self):
        """Строка с нечисловыми данными о курсах (ValueError) пропускается,
        остальные строки в таблице продолжают обрабатываться. Без этого
        одна кривая строка HTML роняла бы весь прогон парсинга страницы."""

        html = """
        <table class="content_table">
          <tbody>
            <tr>
              <td class="bank_name">Плохой Банк</td>
              <td><a href="/bank/bad/currency">ссылка</a></td>
              <td class="USD">н/д</td>
              <td class="USD">н/д</td>
              <td class="EUR">н/д</td>
              <td class="EUR">н/д</td>
              <td><time>26.06.2026 19:04</time></td>
            </tr>
            <tr>
              <td class="bank_name">СберБанк</td>
              <td><a href="/bank/sberbank/currency">ссылка</a></td>
              <td class="USD">74,30</td>
              <td class="USD">78,40</td>
              <td class="EUR">87,70</td>
              <td class="EUR">93,10</td>
              <td><time>26.06.2026 19:04</time></td>
            </tr>
          </tbody>
        </table>
        """
        result = parse_currency_table(html)

        assert len(result) == 1
        assert result[0].bank_en == "sberbank"

    def test_tracker_row_with_listing_is_excluded(self):
        """Строка с трекерной ссылкой s2=listing — обезличенная реклама,
        не привязанная к конкретному банку (из логов видно: 'Инго Банк',
        'Банк Казани', 'Экспобанк' скрываются под listing). Такая строка
        должна полностью исключаться из результата."""

        href = "/go?url=https%3A%2F%2Fmrxe.ru%2F123%3Fs2%3Dlisting"
        result = parse_currency_table(
            make_table_html(bank_name="Инго Банк", href=href)
        )

        assert result == []


class TestFetchHtml:
    """Тесты для fetch_html — получение HTML с повторными попытками.
    Сессия мокается напрямую (передаётся параметром), сети нет."""

    async def test_successful_response_returns_html(self):
        """При успешном ответе сервера функция возвращает текст HTML."""

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = AsyncMock(return_value="<html>тест</html>")

        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        context_manager.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = context_manager

        result = await fetch_html("https://example.com", mock_session)

        assert result == "<html>тест</html>"

    async def test_raises_after_max_retries(self):
        """После исчерпания всех попыток (retries=1 для скорости теста)
        пробрасывает исходное исключение. Без этого сбой сети молча
        вернул бы None вместо реального сигнала об ошибке."""

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=ClientError("сервер недоступен")
        )

        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        context_manager.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = context_manager

        with pytest.raises(ClientError):
            await fetch_html("https://example.com", mock_session, retries=1)


class TestGetLinkInfo:
    """Тесты для get_link_info — разбор ссылки и исключение трекеров."""

    def test_standard_link_returns_url_and_bank_en(self):
        """Обычная ссылка /bank/sberbank/currency корректно
        разбирается на url и bank_en с проверкой поступления
        корректных данных в ссылке (link)."""

        html = '<a href="/bank/sberbank/currency">Сбербанк</a>'
        link = BeautifulSoup(html, "html.parser").find("a")
        url, bank_en = get_link_info(link)
        assert bank_en == "sberbank"
        assert url == "https://ru.myfin.by/bank/sberbank/currency"

    def test_tracker_with_real_bank_en_returns_bank_en(self):
        """Трекерная ссылка с реальным s2=kamkombank — bank_en корректно
        извлекается, банк не теряется."""

        href = "/go?url=https%3A%2F%2Fmrxe.ru%2F123%3Fs2%3Dkamkombank"
        html = f'<a href="{href}">КАМКОМБАНК</a>'
        link = BeautifulSoup(html, "html.parser").find("a")
        url, bank_en = get_link_info(link)
        assert bank_en == "kamkombank"
        assert url is not None

    def test_tracker_with_listing_is_excluded(self):
        """Трекерная ссылка с s2=listing — это обезличенная реклама,
        не привязанная к конкретному банку. Должна вернуть (None, None),
        чтобы parse_currency_table пропустил эту строку таблицы."""

        href = "/go?url=https%3A%2F%2Fmrxe.ru%2F456%3Fs2%3Dlisting"
        html = f'<a href="{href}">Инго Банк</a>'
        link = BeautifulSoup(html, "html.parser").find("a")
        url, bank_en = get_link_info(link)
        assert url is None
        assert bank_en is None