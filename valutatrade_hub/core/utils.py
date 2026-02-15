"""
Утилиты и вспомогательные функции для работы с валютами и валидацией.
"""

import json

# core/validators.py
from datetime import datetime, timedelta
from pathlib import Path
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
        
        dt = datetime.fromisoformat(updated_at)
        age = datetime.utcnow() - dt
        return age <= timedelta(seconds=ttl_seconds)
    except Exception:
        return False


def fetch_rate_from_parser(f_code: str, t_code: str) -> Optional[float]:
    # Здесь должен быть код для получения курса из парсера или API.
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
    rate_key = f"{from_code}_{to_code}"

    # Проверяем прямой курс, используя TTL из SettingsLoader
    if rate_key in rates_data and is_rate_fresh(rates_data[rate_key].get("updated_at", "")):
        rate_data = rates_data[rate_key]
        return float(rate_data["rate"]), rate_data["updated_at"]

    # Проверяем обратный курс (например, USD→BTC вместо BTC→USD)
    rev_key = f"{to_code}_{from_code}"
    if rev_key in rates_data and is_rate_fresh(rates_data[rev_key].get("updated_at", "")):
        rate_data = rates_data[rev_key]
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

    # Сохраняем обновленный курс с временной меткой
    updated_at = datetime.utcnow().replace(microsecond=0).isoformat()
    rates_data[rate_key] = {"rate": float(fetched), "updated_at": updated_at}
    rates_data["last_refresh"] = updated_at
    rates_data["source"] = "ParserService"
    
    db = DatabaseManager()
    db.save_file("rates_file", rates_data)

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
        display_updated = datetime.fromisoformat(updated_at).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        display_updated = updated_at or "N/A"

    rate_str = f"{float(rate):.8f}".rstrip('0').rstrip('.')
    reverse_rate_str = f"{float(reverse_rate):.8f}".rstrip('0').rstrip('.') if reverse_rate is not None else "N/A"

    msg = f"Курс {from_code}→{to_code}: {rate_str} (обновлено: {display_updated})\n"
    if reverse_rate is not None:
        msg += f"Обратный курс {to_code}→{from_code}: {reverse_rate_str}"

    return True, msg, float(rate), updated_at
