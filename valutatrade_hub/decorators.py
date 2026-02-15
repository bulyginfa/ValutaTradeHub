"""
Пользовательские декораторы проекта:
- Логирует операции BUY/SELL/REGISTER/LOGIN.
- Фиксирует исключения, но не скрывает их.
- Достает параметры из сигнатуры функции.

Используется в сервисах для трассировки ключевых действий.
"""

import functools
from inspect import signature
from typing import Any, Callable, Optional, TypeVar

from .logging_config import log_action as log_action_func

F = TypeVar("F", bound=Callable[[Any], Any])


def log_action(
    action_type: Optional[str] = None,
    verbose: bool = False,
) -> Callable[[F], F]:
    """
    Логирование доменных операций и ошибок.

    Args:
        action_type: Явный тип действия; иначе берется имя метода.
        verbose: Добавляет расширенный контекст (если поддержан).
    """
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Определяем имя действия
            action_name = action_type or func.__name__.upper()
            
            # Пытаемся вытащить параметры из аргументов
            log_data = {
                "action": action_name,
                "username": None,
                "user_id": None,
                "currency_code": None,
                "amount": None,
                "rate": None,
                "base": None,
                "wallet_before": None,
                "wallet_after": None,
            }
            
            # Парсим параметры функции
            try:
                sig = signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # Извлекаем значения параметров
                params = bound_args.arguments
                
                # Определяем user_id и username в зависимости от типа метода
                if "user_id" in params:
                    log_data["user_id"] = params["user_id"]
                if "username" in params:
                    log_data["username"] = params["username"]
                
                # Извлекаем валютные параметры
                if "currency" in params:
                    log_data["currency_code"] = params["currency"]
                
                if "amount" in params:
                    log_data["amount"] = params["amount"]
                
                if "base" in params:
                    log_data["base"] = params["base"]
                
            except Exception:
                pass  # Если не удалось спарсить, продолжаем без параметров
            
            # Выполняем функцию и ловим результат или исключение
            try:
                result = func(*args, **kwargs)
                
                # Пытаемся вытащить rate и другие данные из результата
                if isinstance(result, tuple) and len(result) >= 2:
                    success, message = result[0], result[1]
                    log_data["result"] = "OK" if success else "ERROR"
                    
                    # Если это ошибка, пытаемся вытащить текст ошибки
                    if not success and isinstance(message, str):
                        log_data["error_message"] = message
                else:
                    log_data["result"] = "OK"
                
                # Логируем успешное выполнение
                log_action_func(
                    action=log_data["action"],
                    username=log_data.get("username"),
                    user_id=log_data.get("user_id"),
                    currency_code=log_data.get("currency_code"),
                    amount=log_data.get("amount"),
                    rate=log_data.get("rate"),
                    base=log_data.get("base"),
                    result=log_data.get("result", "OK"),
                    error_message=log_data.get("error_message"),
                    wallet_before=log_data.get("wallet_before"),
                    wallet_after=log_data.get("wallet_after"),
                )
                
                return result
                
            except Exception as e:
                # Логируем исключение
                log_action_func(
                    action=log_data["action"],
                    username=log_data.get("username"),
                    user_id=log_data.get("user_id"),
                    currency_code=log_data.get("currency_code"),
                    amount=log_data.get("amount"),
                    rate=log_data.get("rate"),
                    base=log_data.get("base"),
                    result="ERROR",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    wallet_before=log_data.get("wallet_before"),
                    wallet_after=log_data.get("wallet_after"),
                )
                
                # Пробрасываем исключение дальше
                raise
        
        return wrapper
    
    # Если декоратор используется без параметров (@log_action)
    if callable(action_type):
        func = action_type
        action_type = None
        return decorator(func)
    
    return decorator
