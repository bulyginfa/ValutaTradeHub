"""
Основная бизнес-логика проекта.

Модуль содержит два основных сервиса:

1. PortfolioService - управление портфелями пользователей:
   - Создание и загрузка портфелей
   - Операции покупки и продажи валюты
   - Отслеживание кошельков и балансов
   - Вычисление стоимости портфеля в разных валютах

2. UserService - управление пользователями:
   - Регистрация новых пользователей (REGISTER)
   - Аутентификация пользователей (LOGIN)
   - Управление паролями с хешированием
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from prettytable import PrettyTable

from ..decorators import log_action
from ..infra.database import DatabaseManager
from .models import Portfolio, User, Wallet
from .currencies import get_currency
from .utils import get_rate, validate_amount
from ..core.exceptions import InsufficientFundsError

class PortfolioService:
    """
    Сервис управления портфелем пользователя и операциями с валютными кошельками.
    """

    @classmethod
    def _find_portfolio(cls, 
                        data: Dict[str, Any], 
                        user_id: int) -> Optional[Dict[str, Any]]:
        """
        Находит портфель пользователя в загруженных данных.
        
        Args:
            data: Загруженные данные портфелей
            user_id: ID пользователя для поиска
            
        Returns:
            Словарь портфеля если найден, иначе None.
            Обеспечивает безопасное преобразование типов для user_id.
        """
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
        """
        Восстанавливает объект Portfolio из словаря (десериализация).
        
        Преобразует сырые данные из JSON в объекты моделей Portfolio и Wallet.
        Безопасно обрабатывает случаи с отсутствующими или некорректными данными.
        
        Args:
            p_dict: Последовательный портфель из JSON
            user_id: ID пользователя владельца портфеля
            
        Returns:
            Объект Portfolio с восстановленными кошельками (Wallet)
        """
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
    def _save_portfolio(cls, 
                        data: Dict[str, Any], 
                        user_id: int, 
                        portfolio: Portfolio
                        ) -> None:
        """
        Сохраняет объект Portfolio обратно в словарь данных и сохраняет в файл (сериализация).
        
        Преобразует объекты моделей обратно в словари для сохранения в JSON.
        Находит портфель пользователя и обновляет его кошельки.
        
        Args:
            data: Полные данные портфелей для обновления
            user_id: ID пользователя для поиска его портфеля
            portfolio: Объект Portfolio с обновленным состоянием
        """
        new_wallets = {c: {"balance": w.balance} for c, w in portfolio.wallets.items()}
        for idx, p in enumerate(data.get("portfolios", [])):
            try:
                if int(p.get("user_id")) == int(user_id):
                    data["portfolios"][idx]["wallets"] = new_wallets
                    break
            except Exception:
                continue
        db = DatabaseManager()
        db.save_file("portfolios_file", data)

    # -------------------------
    # Основная логика
    # -------------------------

    @classmethod
    def create_portfolio(cls, user_id: int) -> bool:
        """
        Создаёт новый портфель для пользователя с ОБЯЗАТЕЛЬНЫМ USD кошельком.
        
        Если портфель уже существует, просто возвращает True.
        Вызывается при регистрации нового пользователя.
        
        Безопасная операция read-modify-write:
        1. Загружает данные портфелей
        2. Проверяет существование портфеля
        3. Создает новый портфель с USD кошельком в памяти
        4. Сохраняет через DatabaseManager с обработкой ошибок
        
        Args:
            user_id: ID пользователя, для которого создать портфель
            
        Returns:
            True если портфель создан или уже существует, False при ошибке сохранения
        """
        try:
            db = DatabaseManager()
            data = db.load_file("portfolios_file")
            if "portfolios" not in data:
                data["portfolios"] = []
            portfolios = data.get("portfolios", [])

            if any(int(p.get("user_id")) == int(user_id) for p in portfolios):
                return True

            # Создаем портфель с обязательным USD кошельком
            new_portfolio = {
                "user_id": int(user_id),
                "wallets": {
                    "USD": {"balance": 0.0}
                }
            }
            portfolios.append(new_portfolio)
            data["portfolios"] = portfolios
            
            db.save_file("portfolios_file", data)
            return True
        except Exception as e:
            import sys
            print(f"ОШИБКА: create_portfolio() не смог сохранить портфель: {e}", file=sys.stderr)
            return False
    
    @classmethod
    @log_action(action_type="DEPOSIT", verbose=True)
    def deposit_usd(cls, user_id: int, amount: float) -> Tuple[bool, str]:
        """
        Метод пополнения USD кошелька пользователя (поступление средств).
        
        Args:
            user_id: ID пользователя
            amount: Сумма для пополнения USD (положительное число)
            
        Returns:
            Кортеж (success, message)
        """
        amt = validate_amount(amount)
        
        db = DatabaseManager()
        data = db.load_file("portfolios_file")
        if "portfolios" not in data:
            data["portfolios"] = []
        p_dict = cls._find_portfolio(data, user_id)
        if p_dict is None:
            return False, "Портфель не найден"
        
        portfolio = cls._restore_portfolio(p_dict, user_id)
        usd_wallet = portfolio.get_wallet("USD")
        
        if usd_wallet is None:
            return False, "ОШИБКА: USD кошелек отсутствует"
        
        before = usd_wallet.balance
        usd_wallet.deposit(amt)
        after = usd_wallet.balance
        
        try:
            cls._save_portfolio(data, user_id, portfolio)
        except Exception as e:
            return False, f"Ошибка сохранения портфеля: {e}"
        
        amt_str = f"{amt:.2f}"
        before_str = f"{before:.2f}"
        after_str = f"{after:.2f}"
        
        return True, f"Депозит выполнен: +{amt_str} USD\nБаланс было: {before_str} USD → стало: {after_str} USD"

    @classmethod
    def get_portfolio(cls, user_id: int, base: str = "USD") -> Tuple[bool, str, Optional[Portfolio]]:
        """
        Метод для получения портфеля пользователя с расчётом стоимости в базовой валюте.
        
        Загружает информацию пользователя и портфель, считает общую стоимость
        в указанной базовой валюте, используя текущие курсы обмена.
        
        Args:
            user_id: ID пользователя
            base: Базовая валюта для расчёта (по умолчанию USD)
            
        Returns:
            Кортеж (success, message, portfolio_object):
            - success: True если портфель загружен
            - message: Описание портфеля или ошибка
            - portfolio_object: Объект Portfolio или None при ошибке
        """
        # Валидация базовой валюты
        base = get_currency(base).code

        # Загрузка пользователей, чтобы вывести логин.
        db = DatabaseManager()
        users_data = db.load_file("users_file")
        if "users" not in users_data:
            users_data["users"] = []
        
        user = next((u for u in users_data.get("users", []) 
                     if int(u.get("user_id")) == int(user_id)), None)
        username = user.get("username", "Неизвестный") if user else "Неизвестный"
        
        # Загрузка данных портфеля для указанного пользователя.
        data = db.load_file("portfolios_file")
        if "portfolios" not in data:
            data["portfolios"] = []
        
        portfolio_dict = next(
            (p for p in data.get("portfolios", [])
             if int(p.get("user_id")) == int(user_id)), None)
        
        if not portfolio_dict:
            return False, "Портфель не найден", None
        
        wallets = portfolio_dict.get("wallets") or {}
        portfolio_obj = cls._restore_portfolio(portfolio_dict, user_id)

        # Если портфель пустой или кошельков нет, возвращаем сообщение об этом.
        if not isinstance(wallets, dict) or len(wallets) == 0:
            return True, f"Портфель пользователя '{username}' пуст.", portfolio_obj
        
        total_in_base = 0.0
        table = PrettyTable()
        table.field_names = ["Currency","Balance", 
                             f"Value ({base})", 
                             f"Rate ({base}/cur)"]
        table.align = "r"
        
        # Формируем отсортированный список кошельков.
        for currency_code in sorted(wallets.keys()):
            raw = wallets[currency_code]

            if isinstance(raw, dict):
                balance = float(raw.get("balance", 0.0))
            else:
                balance = float(raw)

            
            # Получаем курс currency -> base
            try:
                success, msg, rate, _updated_at = get_rate(currency_code, base)
            except Exception as e:
                msg_err = f"Не удалось получить курс для {currency_code}→{base}: {str(e)}"
                return False, msg_err, None
            
            value_in_base = balance * rate
            total_in_base += value_in_base
            bal_str = f"{balance:.4f}"
            val_str = f"{value_in_base:,.4f}".replace(",", " ")
            
            if currency_code == base:
                rate_str = "1.00"
            else:
                rate_str = f"{rate:,.4f}".replace(",", " ")
            value_with_base = val_str + " " + base
            table.add_row([currency_code, bal_str, value_with_base, rate_str])
        
        total_str = f"{total_in_base:,.2f}".replace(",", " ")
        result = (
            f"Портфель пользователя '{username}' (база: {base}):\n"
            + str(table) + "\n"
            + f"ИТОГО: {total_str} {base}"
        )
        return True, result, portfolio_obj

    
    @classmethod
    @log_action(action_type="BUY", verbose=True)
    def buy(cls, user_id: int, currency: str, amount: float, base: str = "USD") -> Tuple[bool, str]:
        """
        Метод по покупке валюты для пользователя.
        Списание с USD кошелька и пополнение кошелька целевой валюты.
        
        Args:
            user_id: ID пользователя
            currency: Код валюты для покупки (например, BTC, ETH) - НЕ USD!
            amount: Количество валюты для покупки
            base: Базовая валюта (по умолчанию USD, не менять)
            
        Returns:
            Кортеж (success, message) с результатом операции
        """
        code = get_currency(currency).code
        amt = validate_amount(amount)
        
        # Запрет на покупку USD
        if code == "USD":
            return False, "Ошибка: покупать USD через buy нельзя. Используйте deposit для пополнения."
        
        db = DatabaseManager()
        data = db.load_file("portfolios_file")
        if "portfolios" not in data:
            data["portfolios"] = []
        p_dict = cls._find_portfolio(data, user_id)
        if p_dict is None:
            return False, "Портфель не найден"

        portfolio = cls._restore_portfolio(p_dict, user_id)
        
        # Проверка: наличия USD кошелька
        usd_wallet = portfolio.get_wallet("USD")
        if usd_wallet is None:
            return False, "USD кошелек отсутствует. Покупка невозможна."
        
        # Получение курса currency -> USD
        try:
            success, msg, rate, _updated_at = get_rate(code, "USD")
        except Exception as e:
            return False, f"Не удалось получить курс для {code}→USD: {e}"
        
        # Рассчитываем стоимость покупки в USD
        cost_usd = amt * rate
        
        # Проверка достаточной суммы на USD кошельке
        if usd_wallet.balance < cost_usd:
            return False, (f"Недостаточно USD: требуется {cost_usd:.2f}, "
                          f"доступно {usd_wallet.balance:.2f}")
        
        # Списываем сумму с USD кошелька
        try:
            usd_wallet.withdraw(cost_usd)
        except InsufficientFundsError as e:
            return False, str(e)
        
        # Создаем кошелек целевой валюты если его нет
        if code not in portfolio.wallets:
            portfolio.add_currency(code)
        
        target_wallet = portfolio.get_wallet(code)
        if target_wallet is None:
            # Откатываем (восстанавливаем USD)
            usd_wallet.deposit(cost_usd)
            return False, f"Не удалось создать кошелёк для {code}"
        
        # Пополняем кошелек с целевой валютой
        before = target_wallet.balance
        target_wallet.deposit(amt)
        after = target_wallet.balance
        
        #Сохраняем портфель
        try:
            cls._save_portfolio(data, user_id, portfolio)
        except Exception as e:
            usd_wallet.deposit(cost_usd)
            target_wallet.balance = before
            return False, f"Ошибка сохранения портфеля: {e}"
        
        # Формируем сообщение с результатом операции
        rate_str = f"{rate:,.4f}".replace(",", " ")
        cost_str = f"{cost_usd:,.2f}".replace(",", " ")
        amt_str = f"{amt:.4f}"
        usd_balance_str = f"{usd_wallet.balance:.2f}"
        
        msg = (
            f"Покупка выполнена: {amt_str} {code} по курсу {rate_str} USD/{code}\n"
            f"Списано: {cost_str} USD | Баланс USD: {usd_balance_str}"
        )
        return True, msg

    @classmethod
    @log_action(action_type="SELL", verbose=True)
    def sell(cls, user_id: int, currency: str, amount: float, base: str = "USD") -> Tuple[bool, str]:
        """
        Метод по продаже валюты для пользователя.
        Списание с кошелька продаваемой валюты и пополнение USD кошелька.
        
        Args:
            user_id: ID пользователя
            currency: Код валюты для продажи (например, BTC, ETH) - НЕ USD!
            amount: Количество валюты для продажи
            base: Базовая валюта (по умолчанию USD, не менять)
            
        Returns:
            Кортеж (success, message) с результатом операции
            
        Raises:
            InsufficientFundsError: Если недостаточно средств на кошельке
        """
        code = get_currency(currency).code
        amt = validate_amount(amount)
        
        # Запрет на продажу USD
        if code == "USD":
            return False, "Ошибка: продавать USD нельзя."
    
        db = DatabaseManager()
        data = db.load_file("portfolios_file")
        if "portfolios" not in data:
            data["portfolios"] = []
        p_dict = cls._find_portfolio(data, user_id)
        if p_dict is None:
            return False, "Портфель не найден"

        portfolio = cls._restore_portfolio(p_dict, user_id)

        # Проверка наличия кошелька исходной валюты
        if code not in portfolio.wallets:
            return False, f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке."

        wallet = portfolio.get_wallet(code)
        if wallet is None:
            return False, f"Не удалось получить кошелёк для {code}"

        before = wallet.balance
        
        # Проверка достаточности средств на кошельке продаваемой валюты
        try:
            wallet.withdraw(amt)
        except InsufficientFundsError as e:
            return False, str(e)
        
        after = wallet.balance
        
        # Получение курса и расчет выручки
        try:
            success, msg, rate, _updated_at = get_rate(code, "USD")
        except Exception as e:
            wallet.deposit(amt)
            return False, f"Не удалось получить курс: {e}"

        proceeds_usd = amt * rate
        
        # Проверка наличия USD кошелька для зачисления выручки
        usd_wallet = portfolio.get_wallet("USD")
        if usd_wallet is None:
            wallet.deposit(amt)
            return False, "ОШИБКА: USD кошелек отсутствует. Продажа невозможна."
        
        # Зачисляем выручку в USD
        usd_wallet.deposit(proceeds_usd)

        # Сохраняем изменения
        try:
            cls._save_portfolio(data, user_id, portfolio)
        except Exception as e:
            wallet.deposit(amt)
            usd_wallet.withdraw(proceeds_usd)
            return False, f"Ошибка сохранения портфеля при продаже: {e}"

        # Формируем успешное сообщение
        rate_str = f"{rate:,.4f}".replace(",", " ")
        proceeds_str = f"{proceeds_usd:,.2f}".replace(",", " ")
        amt_str = f"{amt:.4f}"
        before_str = f"{before:.4f}"
        after_str = f"{after:.4f}"
        usd_balance_str = f"{usd_wallet.balance:.2f}"

        msg = (
            f"Продажа выполнена: {amt_str} {code} "
            f"по курсу {rate_str} USD/{code}\n"
            f"Выручка: {proceeds_str} USD | Баланс USD: {usd_balance_str}"
        )

        return True, msg


class UserService:
    """
    Сервис управления пользователями.
    
    Класс предоставляет методы для регистрации и аутентификации пользователей
    А также для управления их данными в JSON файле
    Пароли хранятся в виде хешей (SHA256 с солью)
    """
    @staticmethod
    def _next_user_id(users: list[dict]) -> int:
        return max((u["user_id"] for u in users), default=0) + 1

    @staticmethod
    @log_action(action_type="REGISTER")
    def signup(username: str, password: str) -> Tuple[bool, str]:
        """
        Метод регистрации нового пользователя в системе.
        
        Args:
            username: Имя пользователя (должно быть уникально)
            password: Пароль (должен содержать цифру и спецсимвол, мин 4 символа)
            
        Returns:
            Кортеж (success, message) с результатом регистрации
        """
        import json
        try:
            db = DatabaseManager()
            try:
                users_data = db.load_file("users_file")
            except json.JSONDecodeError:
                users_data = {"users": []}
                db.save_file("users_file", users_data)
            if "users" not in users_data:
                users_data["users"] = []
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
            db.save_file("users_file", users_data)
            
            PortfolioService.create_portfolio(user_id)

            return True, (f"Пользователь '{username}' зарегистрирован (id={user_id}). "
                          f"Войдите: login --username {username} --password ****"
                          )
        except Exception as e:
            return False, f"Ошибка регистрации: {e}"

    @staticmethod
    @log_action(action_type="LOGIN")
    def login(username: str, password: str) -> Tuple[bool, str, Optional[int]]:
        """
        Метод аутентификации пользователя.
        
        Args:
            username: Имя пользователя
            password: Пароль пользователя
            
        Returns:
            Кортеж (success, message, user_id):
            - success: True если аутентификация успешна
            - message: Приветственное сообщение или ошибка
            - user_id: ID пользователя (или None при ошибке)
        """
        try:
            db = DatabaseManager()
            users_data = db.load_file("users_file")
            if "users" not in users_data:
                users_data["users"] = []
            users = users_data.get("users", [])

            # Поиск пользователя с заданным именем
            user = next((u for u in users if u.get("username") == username), None)
            
            if not user:
                return False, f"Пользователь '{username}' не найден", None

            # Получение сохранённой соли и хеша
            salt = user.get("salt")
            stored_hashed = user.get("hashed_password")

            if not salt or not stored_hashed:
                return False, "Некорректные данные пользователя", None

            try:
                stored_date = user.get("registration_date")
                reg_date = (
                    datetime.fromisoformat(stored_date)
                    if stored_date else datetime.utcnow()
                )
            except Exception:
                reg_date = datetime.utcnow()

            user_obj = User.__new__(User)
            user_obj._user_id = int(user.get("user_id"))
            user_obj._username = str(user.get("username"))
            user_obj._salt = str(salt)
            user_obj._hashed_password = str(stored_hashed)
            user_obj._registration_date = reg_date

            if not user_obj.verify_password(password):
                return False, "Неверный пароль", None
            
            return True, f"Вы вошли как '{username}'", int(user["user_id"])

        except Exception as e:
            return False, f"Ошибка авторизации: {e}", None