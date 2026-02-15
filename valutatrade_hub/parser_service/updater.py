"""Оркестрация обновления курсов и подготовка данных для CLI."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from .api_clients import CoinGeckoClient, ExchangeRateApiClient
from .config import ParserConfig
from .storage import RatesStorage

logger = logging.getLogger("valutatrade_hub.parser_service")


def compute_display_rows(
    snapshot: dict[str, Any],
    currency_filter: str | None,
    top: int | None,
    base: str,
    crypto_codes: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Сформировать строки вывода для CLI из локального снимка курсов."""
    pairs = snapshot.get("pairs", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(pairs, dict) or not pairs:
        return [], "Локальный кеш курсов пуст. Выполните update-rates."

    base = base.upper()
    currency_filter = currency_filter.upper() if currency_filter else None
    base_usd_rate = 1.0
    if base != "USD":
        # Пересчет выполняется через USD, так как в кеше все пары к USD.
        base_entry = pairs.get(f"{base}_USD")
        if not base_entry or not isinstance(base_entry, dict):
            return [], f"Курс для '{base}' не найден."
        try:
            base_usd_rate = float(base_entry.get("rate"))
        except (TypeError, ValueError):
            return [], f"Курс для '{base}' не найден."
        if base_usd_rate <= 0:
            return [], f"Курс для '{base}' не найден."

    rows: list[dict[str, Any]] = []
    for pair_key, entry in pairs.items():
        if not isinstance(entry, dict):
            continue
        if "_" not in pair_key:
            continue
        from_code, to_code = pair_key.split("_", 1)
        if to_code != "USD":
            continue
        if currency_filter and currency_filter not in (from_code, to_code):
            continue
        try:
            rate_usd = float(entry.get("rate"))
        except (TypeError, ValueError):
            continue
        if rate_usd <= 0:
            continue

        rate = rate_usd if base == "USD" else rate_usd / base_usd_rate
        rows.append(
            {
                "pair": f"{from_code}_{base}",
                "rate": rate,
                "updated_at": entry.get("updated_at"),
                "source": entry.get("source"),
                "from_code": from_code,
            }
        )

    if top is not None:
        crypto_set = {c.upper() for c in (crypto_codes or [])}
        # Фильтруем и сортируем только криптовалюты.
        rows = [row for row in rows if row["from_code"] in crypto_set]
        rows.sort(key=lambda row: row["rate"], reverse=True)
        rows = rows[:top]

    if not rows:
        if currency_filter:
            return [], f"Курс для '{currency_filter}' не найден."
        return [], "Курсы не найдены в локальном кеше."

    return rows, None


class RatesUpdater:
    """Оркестратор обновления курсов из нескольких источников."""
    def __init__(
        self,
        config: ParserConfig | None = None,
        storage: RatesStorage | None = None,
        clients: list[Any] | None = None,
    ) -> None:
        """Подготовить клиентов API и слой хранения."""
        self._config = config or ParserConfig()
        self._storage = storage or RatesStorage(config=self._config)
        if clients is not None:
            # Переупаковка списка клиентов в мапу по source_id.
            self._clients = {c.source_id: c for c in clients}
        else:
            self._clients = {
                "coingecko": CoinGeckoClient(self._config),
                "exchangerate": ExchangeRateApiClient(self._config),
            }

    def run_update(self, source: str | None = None) -> dict[str, Any]:
        """Запустить обновление курсов и вернуть итоговый отчет."""
        logger.info("Запуск обновления курсов. Источник: %s", source)

        clients_to_update = self._select_clients(source)
        all_rates: dict[str, float] = {}
        failed_sources: list[str] = []
        history_added = 0

        for client_name, client in clients_to_update.items():
            try:
                rates = client.fetch_rates()
                all_rates.update(rates)
                history_added += self._storage.save_historical_record(rates, client_name)
                logger.info("%s: Успешно обновлено (%s курсов)", client_name, len(rates))
            except Exception as exc:
                logger.error("%s: Получены ошибки - %s", client_name, exc)
                failed_sources.append(client_name)

        last_refresh = None
        updated_pairs = len(all_rates)
        if all_rates:
            source_str = source if source else "multiple"
            last_refresh = self._storage.save_current_rates(all_rates, source_str)
            logger.info("Запись %s курсов в %s", updated_pairs, self._config.RATES_FILE_PATH)

        ok = len(failed_sources) < len(clients_to_update) and updated_pairs > 0
        return {
            "ok": ok,
            "updated_pairs": updated_pairs,
            "history_added": history_added,
            "failed_sources": failed_sources,
            "last_refresh": last_refresh,
        }

    def _select_clients(self, source: str | None) -> dict[str, Any]:
        """Выбрать клиентов для обновления по имени источника."""
        if source is None:
            return dict(self._clients)

        source = source.strip().lower()
        if source in self._clients:
            return {source: self._clients[source]}
        raise ValueError("Указан неизвестный источник. Используйте 'coingecko' или 'exchangerate'.")
