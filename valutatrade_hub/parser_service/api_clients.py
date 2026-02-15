"""Кклиенты для получения курсов из сторонних сервисов."""

from __future__ import annotations

import time
from abc import ABC
from typing import Dict

import requests

from ..core.exceptions import ApiRequestError
from .config import ParserConfig


class BaseApiClient(ABC):
    """Базовый HTTP-клиент для получения курсов с внешних API."""
    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        # Reuse connections between requests for better latency.
        self._session = requests.Session()

    def fetch_rates(self) -> Dict[str, float]:
        """Загрузить курсы в формате {"CODE_BASE": rate}."""
        raise NotImplementedError

    def _make_request(self, url: str, params: Dict | None = None) -> Dict:
        """Выполнить GET с повторами и вернуть JSON-ответ."""
        for attempt in range(self.config.MAX_RETRIES):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.config.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as exc:
                if attempt == self.config.MAX_RETRIES - 1:
                    raise ApiRequestError(f"Ошибка сети: {exc}") from exc
                # Backoff между попытками запроса.
                time.sleep(self.config.RETRY_DELAY)
        raise ApiRequestError("Превышено число попыток")


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для загрузки курсов криптовалют."""
    source_id = "coingecko"
    source_name = "CoinGecko"

    def fetch_rates(self) -> Dict[str, float]:
        """Получить курсы криптовалют к базовой валюте."""
        base_currency = self.config.BASE_CURRENCY.lower()
        crypto_ids = [
            self.config.CRYPTO_ID_MAP[code]
            for code in self.config.CRYPTO_CURRENCIES
            if code in self.config.CRYPTO_ID_MAP
        ]

        if not crypto_ids:
            return {}

        # API CoinGecko ожидает IDs монет и валюту котировки.
        params = {
            "ids": ",".join(crypto_ids),
            "vs_currencies": base_currency,
        }

        try:
            data = self._make_request(self.config.COINGECKO_URL, params)
            rates: Dict[str, float] = {}

            for crypto_code, crypto_id in self.config.CRYPTO_ID_MAP.items():
                if crypto_id in data and base_currency in data[crypto_id]:
                    rate_key = f"{crypto_code}_{self.config.BASE_CURRENCY}"
                    rates[rate_key] = float(data[crypto_id][base_currency])

            return rates
        except ApiRequestError:
            raise
        except Exception as e:
            raise ApiRequestError(f"Ошибка парсинга ответа CoinGecko: {e}")


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для загрузки курсов фиатных валют."""
    source_id = "exchangerate"
    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> Dict[str, float]:
        """Получить курсы фиатных валют к базовой валюте."""
        api_url = self.config.EXCHANGERATE_API_URL
        api_key = self.config.EXCHANGERATE_API_KEY
        url = f"{api_url}/{api_key}/latest/{self.config.BASE_CURRENCY}"

        try:
            data = self._make_request(url)

            if data.get("result") != "success":
                error_type = data.get("error-type", "Unknown error")
                raise ApiRequestError(f"Ошибка API: {error_type}")

            rates: Dict[str, float] = {}
            conversion_rates = data.get("conversion_rates")
            if not isinstance(conversion_rates, dict):
                conversion_rates = {}
            for currency in self.config.FIAT_CURRENCIES:
                raw_rate = conversion_rates.get(currency)
                if raw_rate is not None:
                    try:
                        raw_rate = float(raw_rate)
                    except (TypeError, ValueError):
                        continue
                    if raw_rate <= 0:
                        continue
                    # API возвращает BASE->CURRENCY, сохраняем CURRENCY->BASE.
                    rate_key = f"{currency}_{self.config.BASE_CURRENCY}"
                    rates[rate_key] = 1.0 / raw_rate

            return rates
        except ApiRequestError:
            raise
        except Exception as exc:
            raise ApiRequestError(f"Ошибка парсинга ответа ExchangeRate-API: {exc}") from exc