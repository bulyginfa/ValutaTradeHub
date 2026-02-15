"""Слой хранения JSON-snapshot'ов и истории"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List

from .config import ParserConfig


class RatesStorage:
    """Чтение и запись текущих и исторических курсов в JSON."""
    def __init__(
        self,
        config: ParserConfig | None = None,
        rates_file_path: str | None = None,
        history_file_path: str | None = None,
    ) -> None:
        """Инициализировать пути хранения и конфигурацию."""
        self.config = config or ParserConfig()
        self.rates_file_path = rates_file_path or self.config.RATES_FILE_PATH
        self.history_file_path = history_file_path or self.config.HISTORY_FILE_PATH
        self._rates_dir = os.path.dirname(self.rates_file_path)
        self._history_dir = os.path.dirname(self.history_file_path)

    def save_current_rates(
        self,
        rates: Dict[str, float],
        source: str,
        last_refresh: str | None = None,
    ) -> str:
        """Сохранить текущий снимок курсов и вернуть timestamp."""
        timestamp = last_refresh or datetime.utcnow().replace(microsecond=0).isoformat()
        # Если обновляем конкретный источник, аккуратно сливаем с имеющимся кешем.
        existing_data = self.load_current_rates()
        existing_pairs = existing_data.get("pairs") if isinstance(existing_data, dict) else None
        existing_pairs = existing_pairs if isinstance(existing_pairs, dict) else {}

        if source != "multiple" and existing_pairs:
            current_pairs = dict(existing_pairs)
            effective_source = "multiple"
        else:
            current_pairs = {}
            effective_source = source

        for pair, rate in rates.items():
            current_pairs[pair] = {
                "rate": rate,
                "updated_at": timestamp,
                "source": source,
            }

        current_data = {
            "pairs": current_pairs,
            "last_refresh": timestamp,
            "source": effective_source,
        }

        self._ensure_dir(self._rates_dir)

        # Пишем во временный файл для атомарной замены.
        temp_file = f"{self.rates_file_path}.tmp"
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(current_data, file, indent=2, ensure_ascii=False)

        os.replace(temp_file, self.rates_file_path)
        return timestamp

    def save_historical_record(
        self,
        rates: Dict[str, float],
        source: str,
        timestamp: str | None = None,
    ) -> int:
        """Добавить записи в историю и вернуть их количество."""
        if not rates:
            return 0

        timestamp = timestamp or datetime.utcnow().replace(microsecond=0).isoformat()
        historical_data = self._load_historical_data()

        for pair, rate in rates.items():
            from_currency, to_currency = pair.split("_")
            record_id = f"{pair}_{timestamp}"

            record = {
                "id": record_id,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": rate,
                "timestamp": timestamp,
                "source": source,
                "meta": {
                    "request_ms": 0,
                    "status_code": 200,
                },
            }

            historical_data.append(record)

        self._save_historical_data(historical_data)
        return len(rates)

    def load_current_rates(self) -> Dict:
        """Загрузить текущий снимок курсов с диска."""
        try:
            with open(self.rates_file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"pairs": {}, "last_refresh": None, "source": None}

    def load_rates_snapshot(self) -> Dict:
        """Синоним load_current_rates для совместимости интерфейсов."""
        return self.load_current_rates()

    def save_rates_snapshot(self, data: Dict) -> None:
        """Сохранить предоставленный снимок курсов на диск."""
        self._ensure_dir(self._rates_dir)
        temp_file = f"{self.rates_file_path}.tmp"
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(temp_file, self.rates_file_path)

    def append_history(self, records: List[Dict]) -> int:
        """Добавить список записей в историю и вернуть их количество."""
        if not records:
            return 0
        historical_data = self._load_historical_data()
        historical_data.extend(records)
        self._save_historical_data(historical_data)
        return len(records)

    def _load_historical_data(self) -> List[Dict]:
        """Загрузить историю курсов, поддерживая старый формат файла."""
        try:
            with open(self.history_file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        if isinstance(data, dict):
            records = data.get("records")
            return list(records) if isinstance(records, list) else []
        if isinstance(data, list):
            return data
        return []

    def _save_historical_data(self, data: List[Dict]) -> None:
        """Сохранить историю курсов в JSON-файл."""
        self._ensure_dir(self._history_dir)

        # Пишем во временный файл для атомарной замены.
        temp_file = f"{self.history_file_path}.tmp"
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        os.replace(temp_file, self.history_file_path)

    @staticmethod
    def _ensure_dir(dir_path: str) -> None:
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
