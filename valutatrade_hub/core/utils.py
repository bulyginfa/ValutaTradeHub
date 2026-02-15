"""
Утилиты и вспомогательные функции для работы с валютами и валидацией.
"""


# core/validators.py
from datetime import datetime, timedelta
from typing import Optional, Tuple

from ..infra.database import DatabaseManager
from .currencies import get_currency
from .exceptions import ApiRequestError


def validate_amount(amount: float) -> float:
    """
    Валидирует количество (сумму) валюты.
    
    Args:
        amount: Количество валюты
    
    Returns:
        Преобразованное в float количество если оно валидно
        
    Raises:
        TypeError: Если amount не число
        ValueError: Если amount не положительное число
    """
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise TypeError("Cумма должна быть числом.")
    if amount <= 0:
        raise ValueError("Cумма должна быть положительным числом.")
    return float(amount)

def is_rate_fresh(updated_at: str, ttl_seconds: Optional[int] = None) -> bool:
    """
    Проверка свежести курса на основе TTL из конфигурации.
    
    Args:
        updated_at: ISO строка времени последнего обновления
        ttl_seconds: Время жизни в секундах. Если None, загружается из SettingsLoader.rates_ttl_seconds
    
    Returns:
        True если курс был обновлён менее чем ttl_seconds назад, False иначе
    """
    if not updated_at:
        return False
    
    try:
        # Если TTL не указан, получаем из конфигурации
        if ttl_seconds is None:
            from ..infra.settings import SettingsLoader
            settings = SettingsLoader()
            ttl_seconds = settings.get("rates_ttl_seconds", 3600)

        dt = _parse_iso_datetime(updated_at)
        if dt is None:
            return False
        age = datetime.utcnow() - dt
        return age <= timedelta(seconds=ttl_seconds)
    except Exception:
        return False


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return datetime.fromisoformat(value)
    except Exception:
        return None


def fetch_rate_from_parser(f_code: str, t_code: str) -> Optional[float]:
    """Try to refresh rates via Parser Service and return a calculated rate."""
    try:
        from ..parser_service.config import ParserConfig
        from ..parser_service.storage import RatesStorage
        from ..parser_service.updater import RatesUpdater
    except Exception:
        return None

    try:
        config = ParserConfig()
        storage = RatesStorage(
            rates_file_path=config.RATES_FILE_PATH,
            history_file_path=config.HISTORY_FILE_PATH,
        )
        updater = RatesUpdater(config=config, storage=storage)
    except Exception:
        return None

    try:
        updater.run_update()
    except Exception:
        return None

    snapshot = storage.load_rates_snapshot()
    pairs = snapshot.get("pairs") if isinstance(snapshot, dict) else None
    pairs = pairs if isinstance(pairs, dict) else {}

    if f_code == t_code:
        return 1.0

    direct_key = f"{f_code}_{t_code}"
    if direct_key in pairs:
        try:
            return float(pairs[direct_key].get("rate"))
        except Exception:
            return None

    from_key = f"{f_code}_USD"
    to_key = f"{t_code}_USD"
    from_entry = pairs.get(from_key)
    to_entry = pairs.get(to_key)

    try:
        from_usd = float(from_entry.get("rate")) if isinstance(from_entry, dict) else None
        to_usd = float(to_entry.get("rate")) if isinstance(to_entry, dict) else None
    except Exception:
        return None

    if f_code == "USD" and to_usd and to_usd > 0:
        return 1.0 / to_usd
    if t_code == "USD" and from_usd and from_usd > 0:
        return from_usd
    if from_usd and to_usd and from_usd > 0 and to_usd > 0:
        return from_usd / to_usd

    return None


def get_fresh_rate(from_currency: str, to_currency: str) -> Tuple[float, str]:
    """
    Получение свежего курса обмена между двумя валютами.
    
    Args:
        from_currency: Исходная валюта
        to_currency: Целевая валюта
    
    Returns:
        Кортеж (rate, updated_at):
            - rate: float - значение курса
            - updated_at: str - ISO строка времени обновления курса
    
    Raises:
        CurrencyNotFoundError: Если запрошена неизвестная валюта
        ApiRequestError: Если курс недоступен и не может быть обновлен
    """
    # Валидация кодов валют
    from_code = get_currency(from_currency).code
    to_code = get_currency(to_currency).code

    
    # Загружаем кешированные курсы через DatabaseManager
    db = DatabaseManager()
    rates_data = db.load_file("rates_file")
    pairs = rates_data.get("pairs") if isinstance(rates_data, dict) else None
    rates_pairs = pairs if isinstance(pairs, dict) else rates_data
    rate_key = f"{from_code}_{to_code}"

    # Проверяем прямой курс, используя TTL из SettingsLoader
    if rate_key in rates_pairs and is_rate_fresh(rates_pairs[rate_key].get("updated_at", "")):
        rate_data = rates_pairs[rate_key]
        return float(rate_data["rate"]), rate_data["updated_at"]

    # Проверяем обратный курс (например, USD→BTC вместо BTC→USD)
    rev_key = f"{to_code}_{from_code}"
    if rev_key in rates_pairs and is_rate_fresh(rates_pairs[rev_key].get("updated_at", "")):
        rate_data = rates_pairs[rev_key]
        try:
            rev_rate = float(rate_data.get("rate"))
            if rev_rate == 0:
                raise ZeroDivisionError()
            return 1.0 / rev_rate, rate_data.get("updated_at", "")
        except Exception:
            pass

    # Курс не найден или устарел - пытаемся обновить через парсер/API
    fetched = fetch_rate_from_parser(from_code, to_code)
    if fetched is None:
        raise ApiRequestError(f"Сервис курсов недоступен для {from_code}→{to_code}")

    # После обновления перечитываем кеш, чтобы не затереть полный снимок.
    refreshed_data = db.load_file("rates_file")
    refreshed_pairs = refreshed_data.get("pairs") if isinstance(refreshed_data, dict) else None
    refreshed_pairs = refreshed_pairs if isinstance(refreshed_pairs, dict) else refreshed_data

    # Если свежий курс уже появился в кеше, возвращаем его без перезаписи файла.
    if isinstance(refreshed_pairs, dict):
        if rate_key in refreshed_pairs and is_rate_fresh(refreshed_pairs[rate_key].get("updated_at", "")):
            rate_data = refreshed_pairs[rate_key]
            return float(rate_data["rate"]), rate_data["updated_at"]

        rev_key = f"{to_code}_{from_code}"
        if rev_key in refreshed_pairs and is_rate_fresh(refreshed_pairs[rev_key].get("updated_at", "")):
            rate_data = refreshed_pairs[rev_key]
            try:
                rev_rate = float(rate_data.get("rate"))
                if rev_rate == 0:
                    raise ZeroDivisionError()
                return 1.0 / rev_rate, rate_data.get("updated_at", "")
            except Exception:
                pass

    # Если кеш не содержит курс, добавляем его в текущий снимок.
    updated_at = datetime.utcnow().replace(microsecond=0).isoformat()
    if isinstance(refreshed_data, dict) and "pairs" in refreshed_data and isinstance(refreshed_data.get("pairs"), dict):
        refreshed_data["pairs"][rate_key] = {"rate": float(fetched), "updated_at": updated_at}
        refreshed_data["last_refresh"] = updated_at
        refreshed_data["source"] = "ParserService"
        db.save_file("rates_file", refreshed_data)
    else:
        # Старый формат кеша без обертки "pairs".
        if not isinstance(refreshed_data, dict):
            refreshed_data = {}
        refreshed_data[rate_key] = {"rate": float(fetched), "updated_at": updated_at}
        refreshed_data["last_refresh"] = updated_at
        refreshed_data["source"] = "ParserService"
        db.save_file("rates_file", refreshed_data)

    return float(fetched), updated_at


def get_rate(from_currency: str, to_currency: str) -> Tuple[bool, str, float, str]:
    """
    Получение курса обмена между двумя валютами.
    
    Args:
        from_currency: Код исходной валюты
        to_currency: Код целевой валюты
    
    Returns:
        Кортеж (success, message, rate, updated_at)
        - success: bool - статус получения курса (True если успешно, False если ошибка)
        - message: str - информационное или ошибочное сообщение
        - rate: float - значение курса
        - updated_at: str - ISO строка времени последнего обновления
    
    Raises:
        ValueError: Если код валюты некорректный
        ApiRequestError: Если курс не найден и недоступен
    """
    # Валидация кодов валют.
    from_code = get_currency(from_currency).code
    to_code = get_currency(to_currency).code

    # Для одинаковых валют курс всегда 1.0.
    if from_code == to_code:
        current_time = datetime.utcnow().replace(microsecond=0).isoformat()
        msg = f"Курс {from_code}→{to_code}: 1.0 (одинаковые валюты)"
        return True, msg, 1.0, current_time

    # Берем свежий курс.
    rate, updated_at = get_fresh_rate(from_code, to_code)

    # Обратный курс рассчитываем от прямого, если он доступен.
    try:
        reverse_rate = 1.0 / float(rate) if float(rate) != 0 else None
    except Exception:
        reverse_rate = None

    try:
        parsed_dt = _parse_iso_datetime(updated_at)
        display_updated = parsed_dt.strftime("%Y-%m-%d %H:%M:%S") if parsed_dt else updated_at
    except Exception:
        display_updated = updated_at or "N/A"

    rate_str = f"{float(rate):.8f}".rstrip('0').rstrip('.')
    reverse_rate_str = f"{float(reverse_rate):.8f}".rstrip('0').rstrip('.') if reverse_rate is not None else "N/A"

    msg = f"Курс {from_code}→{to_code}: {rate_str} (обновлено: {display_updated})\n"
    if reverse_rate is not None:
        msg += f"Обратный курс {to_code}→{from_code}: {reverse_rate_str}"

    return True, msg, float(rate), updated_at
