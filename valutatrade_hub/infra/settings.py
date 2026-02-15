"""
Singleton-класс для централизованной загрузки, объединения и кеширования
настроек приложения из config.json и секции [tool.valutatrade]
в pyproject.toml.

Обеспечивает единый источник конфигурации для всего проекта и позволяет
получать параметры из одного места без повторной загрузки файлов.
"""

import json
from pathlib import Path
from typing import Any, Optional

import tomllib


class SettingsLoader:
    """
    Singleton класс для загрузки и кеширования конфигурации.
    """
    
    _instance: Optional['SettingsLoader'] = None
    _config_cache: dict[str, Any] = {}
    
    def __new__(cls) -> 'SettingsLoader':
        """Создает единственный экземпляр и загружает конфигурацию при первом вызове."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_configuration()
        return cls._instance
    
    def _load_configuration(self) -> None:
        """Загружает конфигурацию из файлов в кеш."""
        default_config_path = Path("config.json")
        if not default_config_path.exists():
            raise FileNotFoundError(
                f"Файл конфигурации по умолчанию не найден: {default_config_path.absolute()}"
            )
        
        self._load_from_config_json(default_config_path)
        
        # Затем загружаем pyproject.toml чтобы проверить наличие config_file
        pyproject_config = self._load_from_pyproject_dict()
        
        # Если в pyproject указан path к config файлу, загружаем ТОЛЬКО из него
        if "config_file" in pyproject_config:
            config_path = Path(pyproject_config["config_file"])
            if not config_path.exists():
                raise FileNotFoundError(
                    f"Файл конфигурации, указанный в pyproject.toml, не найден: {config_path.absolute()}"
                )
            self._load_from_config_json(config_path)
            return  # Используем только конфиг из указанного файла
        
        # Иначе применяем параметры из pyproject.toml поверх дефолтной конфигурации
        self._config_cache.update(pyproject_config)
    
    def _load_from_pyproject_dict(self) -> dict[str, Any]:
        """Читает конфигурацию из [tool.valutatrade] в pyproject.toml."""
        pyproject_path = Path("pyproject.toml")
        
        if not pyproject_path.exists():
            return {}
        
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            
            tool_config = data.get("tool", {}).get("valutatrade", {})
            return dict(tool_config) if tool_config else {}
        except Exception as e:
            print(f"Ошибка при чтении pyproject.toml: {e}")
            return {}
    
    def _load_toml_fallback_dict(self, path: Path) -> dict[str, Any]:
        """Простой TOML fallback для [tool.valutatrade]."""
        config = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                in_section = False
                for line in f:
                    line = line.strip()
                    if line == "[tool.valutatrade]":
                        in_section = True
                        continue
                    if line.startswith("[") and in_section:
                        break
                    if not in_section or not line or line.startswith("#"):
                        continue
                    
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if value.lower() in ("true", "false"):
                            config[key] = value.lower() == "true"
                        elif value.isdigit():
                            config[key] = int(value)
                        else:
                            try:
                                config[key] = float(value)
                            except ValueError:
                                config[key] = value
        except Exception as e:
            print(f"Ошибка при чтении TOML fallback: {e}")
        
        return config
    
    def _load_from_config_json(self, path: Optional[Path] = None) -> None:
        """Загружает конфигурацию из JSON файла."""
        if path is None:
            path = Path("config.json")
        
        if not path.exists():
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            self._config_cache.update(config_data)
        except Exception as e:
            print(f"Ошибка при чтении {path}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение по ключу или default."""
        return self._config_cache.get(key, default)
    
    def get_path(self, key: str) -> Path:
        """Возвращает значение ключа как Path, иначе KeyError."""
        value = self.get(key)
        if value is None:
            raise KeyError(f"Ключ конфигурации '{key}' не найден")
        return Path(value)