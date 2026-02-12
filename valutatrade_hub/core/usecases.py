# /core/usecases.py

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from .models import User, Portfolio, Wallet
from .utils import load_exchange_rate, normalize_currency, validate_amount


class PortfolioService:
    PORTFOLIOS_PATH = Path("data/portfolios.json")

    # -------------------------
    # Работа с хранилищем
    # -------------------------

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        if not cls.PORTFOLIOS_PATH.exists():
            return {"portfolios": []}
        with cls.PORTFOLIOS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def _save(cls, data: Dict[str, Any]) -> None:
        cls.PORTFOLIOS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with cls.PORTFOLIOS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    from typing import Any, Dict, Optional, Tuple

    @classmethod
    def _find_portfolio(cls, data: Dict[str, Any], user_id: int) -> Optional[Dict[str, Any]]:
        portfolios = data.get("portfolios", [])
        for p in portfolios:
            try:
                if int(p.get("user_id")) == int(user_id):
                    return p
            except (TypeError, ValueError):
                continue
        return None

    @classmethod
    def _restore_portfolio(cls, p_dict: Dict[str, Any], user_id: int) -> Portfolio:
        """Восстанавливает объект Portfolio из словаря"""
        wallets_raw = p_dict.get("wallets") or {}
        wallet_objs: dict[str, Wallet] = {}
        for c, raw in wallets_raw.items():
            try:
                bal = float(raw.get("balance")) if isinstance(raw, dict) else float(raw)
            except Exception:
                bal = 0.0
            wallet_objs[str(c).upper()] = Wallet(currency_code=c, balance=bal)
        return Portfolio(user=p_dict.get("user_id", user_id), wallets=wallet_objs)

    @classmethod
    def _save_portfolio(cls, data: Dict[str, Any], user_id: int, portfolio: Portfolio) -> None:
        """Сохраняет Portfolio обратно в данные и сохраняет файл"""
        new_wallets = {c: {"balance": w.balance} for c, w in portfolio.wallets.items()}
        for idx, p in enumerate(data.get("portfolios", [])):
            try:
                if int(p.get("user_id")) == int(user_id):
                    data["portfolios"][idx]["wallets"] = new_wallets
                    break
            except Exception:
                continue
        cls._save(data)

    # -------------------------
    # Основная логика
    # -------------------------

    @classmethod
    def create_portfolio(cls, user_id: int) -> bool:
        """
        Создаёт портфель формата: {"user_id": <int>, "wallets": {}}
        Если уже есть — просто True.
        """
        data = cls._load()
        portfolios = data.get("portfolios", [])

        if any(int(p.get("user_id")) == int(user_id) for p in portfolios):
            return True

        portfolios.append({"user_id": int(user_id), "wallets": {}})
        data["portfolios"] = portfolios
        cls._save(data)
        return True


    @classmethod
    def show_portfolio(cls, user_id: int, base: str = "USD") -> Tuple[bool, str]:
        base = normalize_currency(base)

        # получаем имя пользователя
        users_data = UserService._load()
        user = next((u for u in users_data.get("users", []) if int(u.get("user_id")) == int(user_id)), None)
        username = user.get("username", "Неизвестный") if user else "Неизвестный"

        data = cls._load()
        portfolio = next(
            (p for p in data.get("portfolios", []) if int(p.get("user_id")) == int(user_id)),
            None,
        )
        if not portfolio:
            return False, "Портфель не найден"

        wallets = portfolio.get("wallets") or {}
        if not isinstance(wallets, dict) or len(wallets) == 0:
            return True, f"Портфель пользователя '{username}' пуст."

        lines: list[str] = []
        total_in_base = 0.0

        for currency_code in sorted(wallets.keys()):
            raw = wallets[currency_code]

            if isinstance(raw, dict):
                balance = float(raw.get("balance", 0.0))
            else:
                balance = float(raw)

            rate = load_exchange_rate(currency_code, base)
            if rate is None:
                return False, f"Неизвестная базовая валюта '{base}' или нет курса для {currency_code}→{base}"

            value_in_base = balance * rate
            total_in_base += value_in_base

            bal_str = f"{balance:.4f}"
            val_str = f"{value_in_base:,.4f}".replace(",", " ")
            
            if currency_code == base:
                rate_str = "1.00"
            else:
                rate_str = f"{rate:,.4f}".replace(",", " ")

            lines.append(f"- {currency_code}: {bal_str}  → {val_str} {base} (курс: {rate_str} {base}/{currency_code})")

        total_str = f"{total_in_base:,.2f}".replace(",", " ")

        result = (
            f"Портфель пользователя '{username}' (база: {base}):\n"
            + "\n".join(lines)
            + "\n---------------------------------\n"
            + f"ИТОГО: {total_str} {base}"
        )
        return True, result
    
    @classmethod
    def buy(cls, user_id: int, currency: str, amount: float, base: str = "USD") -> Tuple[bool, str]:
        """Купить валюту: увеличить баланс кошелька на `amount`.

        - Проверяет, что портфель существует (т.е. пользователь залогинен)
        - Валидирует `currency` и `amount`
        - Создаёт кошелёк автоматически при отсутствии
        - Увеличивает баланс и сохраняет изменения
        - Опционально возвращает оценочную стоимость покупки в `base`
        """
        try:
            code = normalize_currency(currency)
        except Exception as e:
            return False, f"Некорректный код валюты: {e}"

        try:
            amt = validate_amount(amount)
        except Exception as e:
            return False, f"Некорректная сумма: {e}"

        data = cls._load()
        p_dict = cls._find_portfolio(data, user_id)
        if p_dict is None:
            return False, "Портфель не найден"

        # Восстановить Portfolio из словаря
        portfolio = cls._restore_portfolio(p_dict, user_id)

        # Создать кошелёк при отсутствии
        if code not in portfolio.wallets:
            portfolio.add_currency(code)

        wallet = portfolio.get_wallet(code)
        if wallet is None:
            return False, f"Не удалось создать кошелёк для {code}"

        before = wallet.balance
        wallet.deposit(amt)
        after = wallet.balance

        # Сохранить Portfolio в файл
        cls._save_portfolio(data, user_id, portfolio)

        # Опционально: оценочная стоимость покупки
        try:
            base_code = normalize_currency(base)
        except Exception:
            base_code = "USD"

        try:
            rate = load_exchange_rate(code, base_code)
            cost = amt * rate
        except Exception:
            rate = None
            cost = None

        amt_str = f"{amt:.4f}"
        before_str = f"{before:.4f}"
        after_str = f"{after:.4f}"

        if rate is not None:
            rate_str = f"{rate:,.4f}".replace(",", " ")
            cost_str = f"{cost:,.4f}".replace(",", " ")
            msg = (
                f"Покупка выполнена: {amt_str} {code} по курсу {rate_str} {base_code}/{code}\n"
                f"Изменения в портфеле:\n"
                f"- {code}: было {before_str} → стало {after_str}\n"
                f"Оценочная стоимость покупки: {cost_str} {base_code}"
            )
        else:
            msg = (
                f"Покупка выполнена: {amt_str} {code}\n"
                f"Изменения в портфеле:\n"
                f"- {code}: было {before_str} → стало {after_str}\n"
                f"Оценочная стоимость покупки: недоступна (нет курса для {code}→{base_code})"
            )

        return True, msg

    @classmethod
    def sell(cls, user_id: int, currency: str, amount: float, base: str = "USD") -> Tuple[bool, str]:
        """Продать валюту: уменьшить баланс кошелька на `amount`.

        - Проверяет, что портфель существует (т.е. пользователь залогинен)
        - Валидирует `currency` и `amount`
        - Проверяет, что кошелёк существует и на нём достаточно средств
        - Уменьшает баланс и сохраняет изменения
        - Опционально возвращает оценочную выручку в `base`
        """
        try:
            code = normalize_currency(currency)
        except Exception as e:
            return False, f"Некорректный код валюты: {e}"

        try:
            amt = validate_amount(amount)
        except Exception as e:
            return False, f"Некорректная сумма: {e}"

        data = cls._load()
        p_dict = cls._find_portfolio(data, user_id)
        if p_dict is None:
            return False, "Портфель не найден"

        # Восстановить Portfolio из словаря
        portfolio = cls._restore_portfolio(p_dict, user_id)

        if code not in portfolio.wallets:
            return False, f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке."

        wallet = portfolio.get_wallet(code)
        if wallet is None:
            return False, f"Не удалось получить кошелёк для {code}"

        before = wallet.balance
        
        try:
            wallet.withdraw(amt)
        except ValueError as e:
            return False, str(e)
        
        after = wallet.balance

        cls._save_portfolio(data, user_id, portfolio)

        try:
            base_code = normalize_currency(base)
        except Exception:
            base_code = "USD"

        try:
            rate = load_exchange_rate(code, base_code)
            revenue = amt * rate
        except Exception:
            rate = None
            revenue = None

        amt_str = f"{amt:.4f}"
        before_str = f"{before:.4f}"
        after_str = f"{after:.4f}"

        if rate is not None:
            rate_str = f"{rate:,.2f}".replace(",", " ")
            revenue_str = f"{revenue:,.2f}".replace(",", " ")
            msg = (
                f"Продажа выполнена: {amt_str} {code} по курсу {rate_str} {base_code}/{code}\n"
                f"Изменения в портфеле:\n"
                f"- {code}: было {before_str} → стало {after_str}\n"
                f"Оценочная выручка: {revenue_str} {base_code}"
            )
        else:
            msg = (
                f"Продажа выполнена: {amt_str} {code}\n"
                f"Изменения в портфеле:\n"
                f"- {code}: было {before_str} → стало {after_str}\n"
                f"Оценочная выручка: недоступна (нет курса для {code}→{base_code})"
            )

        return True, msg

class UserService:
    USERS_PATH = Path("data/users.json")

    # -------------------------
    # Работа с хранилищем
    # -------------------------

    @staticmethod
    def _load() -> Dict[str, Any]:
        if not UserService.USERS_PATH.exists():
            return {"users": []}

        with UserService.USERS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _save(data: Dict[str, Any]) -> None:
        UserService.USERS_PATH.parent.mkdir(parents=True, exist_ok=True)

        with UserService.USERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # -------------------------
    # Вспомогательные методы
    # -------------------------

    @staticmethod
    def _next_user_id(users: list[dict]) -> int:
        return max((u["user_id"] for u in users), default=0) + 1

    # -------------------------
    # Основная логика
    # -------------------------

    @staticmethod
    def signup(username: str, password: str) -> Tuple[bool, str]:
        try:
            users_data = UserService._load()
            users = users_data.get("users", [])

            if any(u.get("username") == username for u in users):
                return False, f"Имя пользователя '{username}' уже занято."

            user_id = UserService._next_user_id(users)

            user = User(
                user_id=user_id,
                username=username,
                password=password,
                registration_date=datetime.utcnow(),
            )

            users.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "hashed_password": user._hashed_password,
                    "salt": user._salt,
                    "registration_date": user.registration_date.isoformat(),
                }
            )

            users_data["users"] = users
            UserService._save(users_data)
            
            PortfolioService.create_portfolio(user_id)

            return True, (f"Пользователь '{username}' зарегистрирован (id={user_id}). "
                          f"Войдите: login --username {username} --password ****"
                          )
        except Exception as e:
            return False, f"Ошибка регистрации: {e}"

    @staticmethod
    def login(username: str, password: str) -> Tuple[bool, str, Optional[int]]:
        try:
            users_data = UserService._load()
            users = users_data.get("users", [])

            user = next((u for u in users if u.get("username") == username), None)
            if user == False:
                return False, f"Пользователь '{username}' не найден", None

            verify_user = User(user['user_id'],
                               username,
                               password,
                               user['registration_date']
                               )
            if verify_user.verify_password(password) == False:
                return False, "Неверный пароль", None
            
            return True, f"Вы вошли как '{username}'", int(user["user_id"])

        except Exception as e:
            return False, f"Ошибка авторизации: {e}", None

    @staticmethod
    def get_rate(from_currency: str, to_currency: str) -> Tuple[bool, str]:
        """Получить текущий курс между двумя валютами.
        
        - Валидирует коды валют
        - Получает курс из локального rates.json
        - Показывает курс в обе стороны и время обновления
        """
        try:
            from_code = normalize_currency(from_currency)
            to_code = normalize_currency(to_currency)
        except Exception as e:
            return False, f"Некорректный код валюты: {e}"

        # Если одна и та же валюта
        if from_code == to_code:
            return True, f"Курс {from_code}→{to_code}: 1.00000000 (одинаковые валюты)"

        try:
            rate = load_exchange_rate(from_code, to_code)
        except Exception:
            return False, f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."

        # Получить обратный курс
        try:
            reverse_rate = load_exchange_rate(to_code, from_code)
        except Exception:
            reverse_rate = None

        # Получить время обновления из rates.json
        try:
            path = Path("data/rates.json")
            with path.open("r", encoding="utf-8") as f:
                rates_data = json.load(f)
            
            pair_key = f"{from_code}_{to_code}"
            updated_at = rates_data.get(pair_key, {}).get("updated_at", "N/A")
        except Exception:
            updated_at = "N/A"

        # Форматирование с удалением нулей на конце
        rate_str = f"{rate:.8f}".rstrip('0').rstrip('.')
        reverse_rate_str = f"{reverse_rate:.8f}".rstrip('0').rstrip('.') if reverse_rate else "N/A"

        msg = f"Курс {from_code}→{to_code}: {rate_str} (обновлено: {updated_at})\n"
        if reverse_rate is not None:
            msg += f"Обратный курс {to_code}→{from_code}: {reverse_rate_str}"

        return True, msg
