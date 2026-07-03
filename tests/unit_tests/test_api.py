from unittest.mock import patch
from app.api.dao import CurrencyRatesDAO

"""
Юнит-тесты для чистых методов CurrencyRatesDAO (которые не используют сессию).

_log_duplicate_banks и _prepare_parsed_records не принимают session и не
делают await session.execute(...), поэтому их можно тестировать полностью
изолированно, без подключения к БД.

Остальные методы CurrencyRatesDAO (требующие session: _fetch_db_banks,
_apply_updates, _apply_inserts, _apply_deactivation, _apply_deletion,
bulk_update_currency, find_best_buy_rates, find_best_sell_rates) сюда
намеренно не входят — для них нужны интеграционные тесты с реальной
(тестовой) БД.
"""

class TestLogDuplicateBanks:
    """Тесты для _log_duplicate_banks — диагностическое логирование дублей."""

    def test_duplicate_bank_name_triggers_warning(self):
        """Дубль по bank_name при РАЗНОМ bank_en — случай 'КАМКОМБАНК'
        (обычная ссылка и рекламный трекер дают разный bank_en) —
        тоже логирует предупреждение с упоминанием названия банка."""
        
        records = [
            {"bank_en": "kamkombank", "bank_name": "КАМКОМБАНК"},
            {"bank_en": "mrxe-tracker", "bank_name": "КАМКОМБАНК"},
        ]
        with patch("app.api.dao.log") as mock_log:
            CurrencyRatesDAO._log_duplicate_banks(records)
            mock_log.warning.assert_called_once()
            message = mock_log.warning.call_args[0][0]
            assert "КАМКОМБАНК" in message

    def test_empty_list_does_not_warn(self):
        """Пустой список записей не вызывает ни ошибок, ни предупреждений."""
        with patch("app.api.dao.log") as mock_log:
            CurrencyRatesDAO._log_duplicate_banks([])
            mock_log.warning.assert_not_called()


class TestPrepareParsedRecords:
    """Тесты для _prepare_parsed_records — фильтрация неполных и
    дублирующихся записей перед дальнейшей обработкой в bulk_update_currency."""

    def test_valid_records_pass_through_unchanged(self):
        """Базовый случай: корректные записи без
        каких-либо проблем. Это "тест на здравомыслие" — он гарантирует,
        что вся защитная логика (фильтрация дублей, проверка на пустые
        поля) не задевает штатные данные."""

        records = [
            {"bank_en": "sberbank", "bank_name": "Сбербанк", "usd_buy": 80.5},
            {"bank_en": "alfabank", "bank_name": "Альфа-Банк", "usd_buy": 81.0},
        ]
        parsed_records, parsed_bank_ens, parsed_bank_names = CurrencyRatesDAO._prepare_parsed_records(records)
        assert parsed_records == records
        assert parsed_bank_ens == {"sberbank", "alfabank"}
        assert parsed_bank_names == {"Сбербанк", "Альфа-Банк"}

    def test_record_without_bank_en_is_skipped(self):
        """Защищает от падения на более поздних шагах: _apply_updates и
        _apply_inserts обращаются к record_dict["bank_en"] напрямую, 
        не через .get() — то есть рассчитывают, что к этому
        моменту bank_en гарантированно есть в каждой записи. Если бы эта
        проверка сломалась, ошибка проявилась бы не здесь, а в виде неясного
        KeyError в совершенно другом, более позднем месте кода."""

        records = [
            {"bank_name": "Сбербанк"},  # нет bank_en
            {"bank_en": "alfabank", "bank_name": "Альфа-Банк"},
        ]
        parsed_records, _, _ = CurrencyRatesDAO._prepare_parsed_records(records)
        assert len(parsed_records) == 1
        assert parsed_records[0]["bank_en"] == "alfabank"

    def test_duplicate_bank_en_keeps_first_occurrence(self):
        """При повторе bank_en в результат попадает 
        именно ПЕРВАЯ встреченная запись, а не последняя."""

        records = [
            {"bank_en": "kamkombank", "bank_name": "КАМКОМБАНК", "usd_buy": 77.99},
            {"bank_en": "kamkombank", "bank_name": "КАМКОМБАНК", "usd_buy": 78.50},
        ]
        parsed_records, parsed_bank_ens, _ = CurrencyRatesDAO._prepare_parsed_records(records)
        assert len(parsed_records) == 1
        assert parsed_records[0]["usd_buy"] == 77.99  # сохранилась именно ПЕРВАЯ запись
        assert parsed_bank_ens == {"kamkombank"}