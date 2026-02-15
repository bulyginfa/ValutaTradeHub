"""
Singleton класс DatabaseManager — единая точка доступа к JSON-хранилищу приложения.
Инкапсулирует чтение и запись данных, отделяя файловую логику от бизнес-слоя.
Пути к файлам берутся из SettingsLoader.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .settings import SettingsLoader


class DatabaseManager:
    """
    Singleton для работы с JSON-хранилищем приложения.

    - Изолирует файловые операции от бизнес-логики
    - Дает единый доступ к данным по ключам конфигурации

    Почему Singleton через __new__:
    - Прозрачно показывает создание единственного экземпляра
    - Проще и легче для отладки, чем метакласс
    """
    
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls) -> 'DatabaseManager':
        """
        Гарантия единственного экземпляра DatabaseManager
        При следующих вызовах возвращает существующий экземпляр.
        
        Returns:
            Экземпляр DatabaseManager
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_file_path(self, config_key: str) -> Path:
        """
        Получение пути к файлу из конфигурации SettingsLoader.
        
        Args:
            config_key: Ключ в конфигурации (например, "portfolios_file")
            
        Returns:
            Path объект к файлу
            
        Raises:
            KeyError: Если ключа конфигурации не существует
        """
        settings = SettingsLoader()
        path = settings.get_path(config_key)
        if path is None:
            raise KeyError(f"Ключ конфигурации '{config_key}' не найден в SettingsLoader")
        return path
    
    def load_file(self, config_key: str) -> Dict[str, Any]:
        """
        Загрузка данных из JSON файла.
        
        Args:
            config_key: Ключ конфигурации пути к файлу
            
        Returns:
            Словарь с данными из JSON файла или пустой {} если файла нет
            
        Raises:
            KeyError: Если ключа конфигурации не существует
            json.JSONDecodeError: Если JSON файл повреждён
        """
        try:
            file_path = self._get_file_path(config_key)
        except KeyError:
            raise KeyError(f"Путь для ключа '{config_key}' не определён в конфигурации")
        
        # Если файла не существует, возвращаем пустой словарь
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Ошибка парсинга JSON файла {file_path}: {e.msg}",
                e.doc,
                e.pos
            )
        except Exception as e:
            raise Exception(f"Ошибка при чтении {file_path}: {e}")
    
    def save_file(self, config_key: str, data: Dict[str, Any]) -> None:
        """
        Сохранение данных в JSON файл.
        
        Args:
            config_key: Ключ конфигурации пути к файлу
                       (например, "portfolios_file", "users_file")
            data: Словарь данных для сохранения в JSON
            
        Raises:
            KeyError: Если ключа конфигурации не существует
            Exception: Если ошибка при записи файла
        """
        try:
            file_path = self._get_file_path(config_key)
        except KeyError:
            raise KeyError(f"Путь для ключа '{config_key}' не определён в конфигурации")
        
        # Создание родительских директорий если их нет
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Ошибка при записи {file_path}: {e}")
    
    def exists(self, config_key: str) -> bool:
        """
        Проверка существования файла по ключу конфигурации.
        
        Args:
            config_key: Ключ конфигурации пути к файлу
            
        Returns:
            True если файл существует, False иначе
        """
        try:
            file_path = self._get_file_path(config_key)
            return file_path.exists()
        except KeyError:
            return False
    
    def __repr__(self) -> str:
        """Строковое представление объекта для отладки."""
        return f"<DatabaseManager at {hex(id(self))}>"
