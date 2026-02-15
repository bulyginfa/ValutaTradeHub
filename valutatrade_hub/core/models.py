"""
Основные модели данных приложения.

Содержит три ключевых класса:

1. User - представляет пользователя системы:
   - Хранит информацию о пользователе (ID, имя, пароль)
   - Управляет хешированием и проверкой пароля

2. Wallet - представляет кошелёк пользователя в определённой валюте:
   - Хранит код валюты и баланс
   - Предоставляет операции пополнения (deposit) и снятия (withdraw)
   - Проверяет достаточность средств при снятии

3. Portfolio - представляет портфель пользователя:
   - Содержит словарь кошельков (по кодам валют)
   - Позволяет добавлять новые валюты
   - Вычисляет общую стоимость портфеля в разных валютах
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from .currencies import get_currency
from .exceptions import InsufficientFundsError
from .utils import get_rate, validate_amount


class User:
    """
    Модель пользователя системы.
    
    Хранит информацию о пользователе и управляет аутентификацией.
    
    Attributes (private):
        _user_id: Уникальный идентификатор пользователя
        _username: Имя пользователя (должно быть уникально)
        _salt: Случайная строка для хеширования пароля
        _hashed_password: Хеш пароля (SHA256)
        _registration_date: Дата и время регистрации (UTC)
    """
    
    def __init__(self, user_id: int, username: str, password: str, registration_date: datetime,) -> None:
        self._user_id = int(user_id)
        self._username = self._check_username(username)
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._make_hash(password)
        self._registration_date = registration_date

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    @staticmethod
    def _check_username(value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("Логин не может быть пустым.")
        return str(value).strip()

    @staticmethod
    def _check_password(value: str) -> str:
        """Вспомогательный метод для проверки сложности пароля."""
        value = "" if value is None else str(value)
        if len(value) < 4:
            raise ValueError("Пароль должен быть не менее 4 символов.")
        return value

    def _make_hash(self, password: str) -> str:
        """Метод создания хеша пароля с солью."""
        password = self._check_password(password)
        payload = (password + self._salt).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get_user_info(self) -> Dict[str, Any]:
        """Информация о пользователе без пароля"""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Изменение пароля пользователя с обновлением соли и хеша"""
        pwd = self._check_password(new_password)
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._make_hash(pwd)

    def verify_password(self, password: str) -> bool:
        """Проверка пароля на совпадение с сохранённым хешем"""
        if password is None:
            return False
        payload = (str(password) + self._salt).encode("utf-8")
        check_hash = hashlib.sha256(payload).hexdigest()
        return check_hash == self._hashed_password


class Wallet:
    """
    Модель кошелька пользователя для конкретной валюты.
    
    Представляет счёт пользователя в определённой валюте:
    - Хранит код валюты
    - Хранит баланс (количество валюты на счёте)
    - Предоставляет операции пополнения и снятия средств
    
    Attributes:
        _currency_code: Код валюты
        balance: Текущий баланс кошелька
    """
    
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self._currency_code = get_currency(currency_code).code
        self.balance = balance  # через сеттер
    
    def deposit(self, amount: float) -> None:
        """
        Пополняет баланс кошелька на указанную сумму.
        
        Args:
            amount: Количество валюты для пополнения (должно быть положительным)
        """
        amount = validate_amount(amount)
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """
        Снимает средства с кошелька.
        Проверяет что на счёте достаточно средств.
        
        Args:
            amount: Количество валюты для снятия
            
        Raises:
            InsufficientFundsError: Если баланс меньше требуемой суммы
        """
        amount = validate_amount(amount)

        if amount > self._balance:
            raise InsufficientFundsError(
                available=self._balance, required=amount, code=self._currency_code
            )

        self._balance -= amount

    def get_balance_info(self) -> Dict[str, Any]:
        """Информация по балансу"""
        return {
            "currency_code": self._currency_code,
            "balance": self._balance,
        }

    @property
    def currency_code(self) -> str:
        return self._currency_code

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)


class Portfolio:
    """
    Модель портфеля пользователя.
    
    Содержит коллекцию кошельков в разных валютах:
    - Хранит объект пользователя-владельца
    - Содержит словарь Wallet объектов (ключи - коды валют)
    - Позволяет добавлять новые валюты (кошельки)
    - Вычисляет общую стоимость портфеля в разных валютах
    
    Каждый кошелек (Wallet) хранит баланс в одной валюте.
    
    Attributes:
        _user: Объект User - владелец портфеля
        _user_id: ID пользователя для быстрого доступа
        _wallets: Словарь кошельков {"код_валюты": Wallet}
    """
    
    def __init__(self, user: Any, wallets: Dict[str, "Wallet"] = None) -> None:
        self._user = user
        self._user_id = int(getattr(user, "user_id", user))
        self._wallets: Dict[str, Wallet] = {}

        if wallets:
            for code, wallet in wallets.items():
                norm = str(code).strip().upper()
                if not isinstance(wallet, Wallet):
                    raise ValueError("wallets должен содержать объекты Wallet.")
                self._wallets[norm] = wallet
    @property
    def user(self) -> Any:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, "Wallet"]:
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """
        Добавление нового валютного кошелька в портфель. 
        Если такой валютный кошелек уже есть, возвращает существующий.
        """
        code = get_currency(currency_code).code

        if not code:
            raise ValueError("Код валюты не может быть пустым.")

        if code in self._wallets:
            return self._wallets[code]

        wallet = Wallet(currency_code=code, balance=0.0)
        self._wallets[code] = wallet
        return wallet


    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        """Получение кошелька по коду валюты. Возвращает None если кошелька нет."""
        code = get_currency(currency_code).code
        return self._wallets.get(code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Получение общей стоимости портфеля в указанной базовой валюте (по курсам обмена)"""
        base = get_currency(base_currency).code
        
        total = 0.0

        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            else:
                success, msg, rate, _updated_at = get_rate(code, base)
                if not success:
                    raise ValueError(f"Не удалось получить курс для {code}→{base}: {msg}")
                total += wallet.balance * rate

        return float(total)