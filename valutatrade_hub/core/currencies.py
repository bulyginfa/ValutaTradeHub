"""
Модуль для работы с валютами.

Модуль определяет абстрактный класс Currency и его реализации
для фиатных и крипто валют.
"""

from __future__ import annotations

import abc
from typing import Dict

from .exceptions import CurrencyNotFoundError


class Currency(abc.ABC):
    """Абстрактный класс для валют.

    Определяет базовую структуру и поведение для всех типов валют.

    Атрибуты (public):
    - name: str — читаемое имя валюты
    - code: str — код валюты. (Валидируется и приводится к верхнему регистру)

    Абстрактный метод:
    - get_display_info(): возвращает форматированное описание валюты для вывода.
    """

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code

    @property
    def name(self) -> str:
        """Получение названия валюты."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Установка названия валюты с валидацией.
        
        Проверяет, что значение не пустое. Автоматически удаляет
        пробелы в начале и конце строки.
        
        Args:
            value: новое название валюты
            
        Raises:
            ValueError: если значение пустое или None
        """
        if value is None or not str(value).strip():
            raise ValueError("name не может быть пустой строкой")
        self._name = str(value).strip()

    @property
    def code(self) -> str:
        """Получение кода валюты (всегда в верхнем регистре)."""
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        """Установка кода валюты с валидацией.
        
        Выполняет следующие действия для обеспечения корректности кода:
        - Проверка, что значение (код) не пустое
        - Преобразует значение (код) в верхний регистр
        - Проверка на наличие пробелов
        - Проверка на длину (2–5 символов)
        
        Args:
            value: новый код валюты
            
        Raises:
            ValueError: если код не соответствует требованиям
        """
        if value is None:
            raise ValueError("Код валюты не может быть пустым")
        v = str(value).strip().upper()
        if " " in v:
            raise ValueError("Код валюты не должен содержать пробелов")
        if not (2 <= len(v) <= 5):
            raise ValueError("Код валюты должен быть длиной 2–5 символов")
        if not v.isalpha():
            raise ValueError(
                f"Код валюты '{v}' должен состоять только из латинских букв (например: USD, EUR, BTC)."
            )
        self._code = v

    @abc.abstractmethod
    def get_display_info(self) -> str:
        """
        Получение форматированного вывода с описанием валюты.
        
        Returns:
            str: форматированное описание валюты
        """
        raise NotImplementedError


class FiatCurrency(Currency):
    """
    Фиатная валюта.
    Расширение базового класса Currency информацией о стране-эмитенте.

    Доп. атрибут:
    - issuing_country: str — название страны или зоны, выпустившей валюту
    """

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        """
        Инициализация фиатной валюты.
        
        Args:
            name: читаемое название валюты
            code: код валюты
            issuing_country: название страны-эмитента
            
        Raises:
            ValueError: если параметры не соответствуют требованиям
        """
        super().__init__(name=name, code=code)
        if issuing_country is None or not str(issuing_country).strip():
            raise ValueError("issuing_country не может быть пустым")
        self.issuing_country = str(issuing_country).strip()

    def get_display_info(self) -> str:
        """
        Отформатированное описание фиатной валюты.
        
        Returns:
            str: строка вида "[FIAT] USD — US Dollar (Issuing: United States)"
        """
        return (
            f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"
        )


class CryptoCurrency(Currency):
    """
    Криптовалюта.
    
    Расширение базового класса Currency c информацией об алгоритме и капитализации валюты.

    Доп. атрибуты:
    - algorithm: str — криптографический алгоритм, используемый криптовалютой.
    - market_cap: float — рыночная капитализация.
    """

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        """
        Инициализация криптовалюты.
        
        Args:
            name: читаемое название валюты
            code: код валюты
            algorithm: криптографический алгоритм
            market_cap: рыночная капитализация (неотрицательное число)
            
        Raises:
            ValueError: если параметры не соответствуют требованиям
        """
        super().__init__(name=name, code=code)
        if algorithm is None or not str(algorithm).strip():
            raise ValueError("algorithm не может быть пустым")
        try:
            mcap = float(market_cap)
        except Exception:
            raise ValueError("market_cap должен быть числом")
        if mcap < 0:
            raise ValueError("market_cap не может быть отрицательным")

        self.algorithm = str(algorithm).strip()
        self.market_cap = float(mcap)

    def get_display_info(self) -> str:
        """
        Отформатированный вывод с описанием криптовалюты.
        
        Returns:
            str: строка вида "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e+12)"
        """
        mcap_str = f"{self.market_cap:.2e}"
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap_str})"
        )

# Глобальный реестр зарегистрированных валют
# Ключ: код валюты в верхнем регистре ("USD", "BTC")
# Значение: объект Currency
_registried_currencies: Dict[str, Currency] = {}

def register_currency(currency: Currency) -> None:
    """
    Регистрация валюты в глобальном реестре.
    
    Позволяет централизованно управлять валютами и легко получать их по коду.
    Каждая валюта хранится по своему коду в верхнем регистре.
    
    Args:
        currency: объект Currency для регистрации
        
    Raises:
        TypeError: если переданный объект не является экземпляром Currency
    """
    if not isinstance(currency, Currency):
        raise TypeError("currency должен быть экземпляром Currency")
    
    _registried_currencies[currency.code] = currency


def get_currency(code: str) -> Currency:
    """
    Получение валюты из реестра по коду.
    
    Выполняет поиск валюты в глобальном реестре по коду.
    
    Args:
        code: код валюты
        
    Returns:
        Currency: найденный объект валюты
        
    Raises:
        CurrencyNotFoundError: если валюта с указанным кодом не зарегистрирована
    """
    key = str(code).strip().upper()
    currency = _registried_currencies.get(key)
    if currency is None:
        raise CurrencyNotFoundError(key)
    return currency
    

# ============================================================================
# Инициализация предопределённых валют
# ============================================================================
# Следующие секции регистрируют основные валюты, которые будут доступны в приложении по умолчанию. 
# 
# Валюты разделены на две категории:
# - фиатные валюты (государственные денежные единицы)
# - криптовалюты (цифровые активы)
# ============================================================================

# Фиатные валюты (государственные)
register_currency(FiatCurrency(name="US Dollar", code="USD", issuing_country="United States"))
register_currency(FiatCurrency(name="Euro", code="EUR", issuing_country="Eurozone"))
register_currency(FiatCurrency(name="Russian Ruble", code="RUB", issuing_country="Russian Federation"))
register_currency(FiatCurrency(name="British Pound", code="GBP", issuing_country="United Kingdom"))
register_currency(FiatCurrency(name="Japanese Yen", code="JPY", issuing_country="Japan"))
register_currency(FiatCurrency(name="Chinese Yuan", code="CNY", issuing_country="China"))

# Криптовалюты
register_currency(CryptoCurrency(name="Bitcoin", code="BTC", algorithm="SHA-256", market_cap=1.12e12))
register_currency(CryptoCurrency(name="Ethereum", code="ETH", algorithm="Ethash", market_cap=4.5e11))
