from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from .utils import load_exchange_rate, normalize_currency, validate_amount


class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        password: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = int(user_id)
        self._username = username 
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._make_hash(password)
        self._registration_date = registration_date

    # -------------------------
    # Вспомогательные методы
    # -------------------------

    @staticmethod
    def _check_username(value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("Логин не может быть пустым.")
        return str(value).strip()

    @staticmethod
    def _check_password(value: str) -> str:
        value = "" if value is None else str(value)
        pattern = r"^(?=.*\d)(?=.*[!@#$%^&*()_\-+=\[{\]};:'\",.<>/?\\|`~]).{4,}$"
        if not re.match(pattern, value):
            raise ValueError("Пароль должен быть не менее 4 символов и содержать "
                             "хотя бы одну цифру и один спецсимвол."
                            )
        return value

    def _make_hash(self, password: str) -> str:
        password = self._check_password(password)
        payload = (password + self._salt).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    # ------------------------
    # Public методы
    # ------------------------
    def get_user_info(self) -> Dict:
        """Информация о пользователе без пароля"""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Меняет пароль: генерируем новую соль и новый псевдо-хеш"""
        pwd = self._check_password(new_password)
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._make_hash(pwd)

    def verify_password(self, password: str) -> bool:
        """Проверка пароля на совпадение с сохранённым хешем"""
        pwd = self._check_password(password)
        return self._make_hash(pwd) == self._hashed_password

    # ------------------------
    # Геттеры
    # ------------------------
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = self._check_username(value)

    @property
    def registration_date(self) -> datetime:
        return self._registration_date


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self._currency_code = normalize_currency(currency_code)
        self.balance = balance  # через сеттер

    # -------------------------
    # Public методы
    # -------------------------
    def deposit(self, amount: float) -> None:
        """Пополнение баланса"""
        amount = validate_amount(amount)
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """Снятие средств при достаточном остатке"""
        amount = validate_amount(amount)

        if amount > self._balance:
            raise ValueError(f"Недостаточно средств: доступно {self._balance}"
                             f", требуется {amount}."
                            )

        self._balance -= amount

    def get_balance_info(self) -> Dict[str, Any]:
        """Информация по балансу"""
        return {
            "currency_code": self._currency_code,
            "balance": self._balance,
        }

    # -------------------------
    # Геттеры / сеттеры
    # -------------------------
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

    # -------------------------
    # Геттеры
    # -------------------------
    @property
    def user(self) -> Any:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, "Wallet"]:
        return dict(self._wallets)

    # -------------------------
    # Базовые операции
    # -------------------------
    def add_currency(self, currency_code: str) -> Wallet:
        code = normalize_currency(currency_code)

        if not code:
            raise ValueError("Код валюты не может быть пустым.")

        if code in self._wallets:
            return self._wallets[code]

        wallet = Wallet(currency_code=code, balance=0.0)
        self._wallets[code] = wallet
        return wallet


    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        code = normalize_currency(currency_code)
        return self._wallets.get(code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        base = normalize_currency(base_currency)
        
        total = 0.0

        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            else:
                rate = load_exchange_rate(code, base_currency)
                if rate is None:
                    raise ValueError(f"Не удалось получить курс для {code}→{base}")
                total += wallet.balance * rate

        return float(total)