"""
Конфигурация логирования для приложения.

Главное:
- Форматтеры JSON и человекочитаемый.
- Настройка логгера с ротацией файлов.
- Структурированные логи действий (BUY/SELL/LOGIN/REGISTER).
"""

import json
import logging
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from .infra.settings import SettingsLoader


class JSONFormatter(logging.Formatter):
    """Форматирует логи в JSON формате для удобного парсирования."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Добавляем дополнительные поля из record, если есть
        if hasattr(record, "action_data"):
            log_data.update(record.action_data)
        
        return json.dumps(log_data, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """Форматирует логи в удобном для чтения формате."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().isoformat() + "Z"
        level = record.levelname
        message = record.getMessage()
        
        # Если есть данные действия, форматируем их красиво
        if hasattr(record, "action_data"):
            data = record.action_data
            parts = [f"{timestamp} {level}"]
            
            # Добавляем основные поля в определённом порядке
            if "action" in data:
                parts.append(f"action={data['action']}")
            if "username" in data:
                parts.append(f"username='{data['username']}'")
            if "user_id" in data:
                parts.append(f"user_id={data['user_id']}")
            if "currency_code" in data:
                parts.append(f"currency='{data['currency_code']}'")
            if "amount" in data:
                parts.append(f"amount={data['amount']}")
            if "rate" in data and data["rate"] is not None:
                parts.append(f"rate={data['rate']:.4f}")
            if "base" in data:
                parts.append(f"base='{data['base']}'")
            if "result" in data:
                parts.append(f"result={data['result']}")
            if "error_type" in data:
                parts.append(f"error_type={data['error_type']}")
            if "error_message" in data:
                parts.append(f"error_message='{data['error_message']}'")
            
            # Добавляем verbose информацию, если есть
            if "wallet_before" in data or "wallet_after" in data:
                if "wallet_before" in data:
                    parts.append(f"wallet_before={data['wallet_before']}")
                if "wallet_after" in data:
                    parts.append(f"wallet_after={data['wallet_after']}")
            
            return " ".join(parts)
        
        return f"{timestamp} {level} {message}"


def setup_logging(
    log_format: str = "human",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation_type: str = "time",  # "time" или "size"
) -> logging.Logger:
    """
    Настраивает логгер и формат вывода.

    Args:
        log_format: Формат логирования ("human" или "json")
        log_level: Уровень логирования ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: Путь к файлу логов (если None, логируется только в консоль)
        rotation_type: Тип ротации ("time" для дневной ротации или "size" для ротации по размеру)
    
    Returns:
        Настроенный logger
    """
    
    # Создаём логгер для приложения
    logger = logging.getLogger("valutatrade_hub")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Удаляем существующие обработчики, чтобы избежать дублирования
    logger.handlers.clear()
    
    # Выбираем форматер в зависимости от параметра
    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    # Добавляем обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Если указан файл логов, добавляем файловый обработчик с ротацией
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        if rotation_type.lower() == "time":
            # Ротация по времени: ежедневное создание нового файла
            file_handler = TimedRotatingFileHandler(
                filename=str(log_path),
                when="midnight",
                interval=1,
                backupCount=30,  # Храним логи за 30 дней
                encoding="utf-8"
            )
            # Форматируем имя файла с датой: actions.log.2025-10-09
            file_handler.suffix = "%Y-%m-%d"
            file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        else:
            # Ротация по размеру: переворачиваем при достижении 10MB
            file_handler = RotatingFileHandler(filename=str(log_path),
                                               maxBytes=10 * 1024 * 1024,  # 10 MB
                                               backupCount=10,  # Храним 10 старых файлов
                                               encoding="utf-8"
                                               )
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Создаём глобальный logger с конфигурацией из SettingsLoader (Singleton)
def _init_action_logger():
    """Инициализирует глобальный logger с конфигурацией из SettingsLoader."""
    settings = SettingsLoader()
    return setup_logging(
        log_format=settings.get("log_format", "human"),
        log_level=settings.get("log_level", "INFO"),
        log_file=settings.get("log_file"),
        rotation_type="time"
    )

action_logger = _init_action_logger()


def log_action(
    action: str,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    currency_code: Optional[str] = None,
    amount: Optional[float] = None,
    rate: Optional[float] = None,
    base: Optional[str] = None,
    result: str = "OK",
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    wallet_before: Optional[float] = None,
    wallet_after: Optional[float] = None,
) -> None:
    """
    Логирует доменное действие со структурированными данными.
    
    Args:
        action: Тип действия (BUY, SELL, REGISTER, LOGIN)
        username: Имя пользователя (если применимо)
        user_id: ID пользователя
        currency_code: Код валюты
        amount: Количество валюты
        rate: Курс обмена (если применимо)
        base: Базовая валюта (если применимо)
        result: Результат операции (OK или ERROR)
        error_type: Тип ошибки (если произошла ошибка)
        error_message: Сообщение об ошибке
        wallet_before: Баланс кошелька до операции (для verbose)
        wallet_after: Баланс кошелька после операции (для verbose)
    """
    
    action_data: Dict[str, Any] = {
        "action": action,
        "result": result,
    }
    
    if username:
        action_data["username"] = username
    if user_id is not None:
        action_data["user_id"] = user_id
    if currency_code:
        action_data["currency_code"] = currency_code
    if amount is not None:
        action_data["amount"] = amount
    if rate is not None:
        action_data["rate"] = rate
    if base:
        action_data["base"] = base
    if error_type:
        action_data["error_type"] = error_type
    if error_message:
        action_data["error_message"] = error_message
    if wallet_before is not None:
        action_data["wallet_before"] = wallet_before
    if wallet_after is not None:
        action_data["wallet_after"] = wallet_after
    
    # Создаём record с дополнительными данными
    record = action_logger.makeRecord(name=action_logger.name,
                                      level=logging.INFO,
                                      fn="",
                                      lno=0,
                                      msg="",
                                      args=(),
                                      exc_info=None
                                      )
    record.action_data = action_data
    
    action_logger.handle(record)
