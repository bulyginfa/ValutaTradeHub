"""
Интерфейс командной строки приложения ValutaTrade Hub.

Предоставляет пользовательский интерфейс для работы с портфелями и операциями:
- register - Регистрация нового пользователя
- login - Вход в систему
- show-portfolio - Просмотр своего портфеля
- buy - Покупка валюты
- sell - Продажа валюты
- get-rate - Получение текущего курса между двумя валютами
- help - Справка по командам
- exit/quit - Выход из приложения

Каждая команда парсится и обрабатывается отдельным методом.
Состояние аутентификации (current_user) хранится в объекте интерфейса.
"""

import argparse
import shlex
from typing import Optional

from ..core.currencies import _registried_currencies
from ..core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from ..core.usecases import PortfolioService, UserService
from ..core.utils import get_rate


class _SilentArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)

    def exit(self, status: int = 0, message: Optional[str] = None) -> None:
        raise ValueError(message or "")


class CLIInterface:
    """
    Основной CLI интерфейс приложения.
    
    Обрабатывает команды пользователя и делегирует их соответствующим
    сервисам (PortfolioService, UserService).
    
    Attributes:
        current_user: ID текущего аутентифицированного пользователя (или None)
    """
    
    def __init__(self) -> None:
        self.current_user: Optional[int] = None

    def process_command(self, command_string: str) -> str:
        """
        Парсит и обрабатывает команду пользователя.
        
        Использует shlex для правильного разбора команд с кавычками и пробелами.
        Возвращает результат выполнения команды или сообщение об ошибке.
        
        Args:
            command_string: Строка с командой (например, "buy --currency BTC --amount 0.05")
        
        Returns:
            Результат выполнения команды или сообщение об ошибке
        """
        args = shlex.split(command_string)
        if not args:
            return ""

        command = args[0].lower()
        tail = args[1:]

        if command in ("exit", "quit"):
            return "exit"
        if command == "help":
            return self._help()
        if command == "register":
            return self._signup(tail)
        if command == "login":
            return self._login(tail)
        if command == "show-portfolio":
            return self._show_portfolio(tail)
        if command == "buy":
            return self._buy(tail)
        if command == "sell":
            return self._sell(tail)
        if command == "deposit":
            return self._deposit(tail)
        if command == "get-rate":
            return self._get_rate(tail)
        if command == "list-currencies":
            return self._list_currencies()

        return f"Неизвестная команда: {command}. Введите 'help' для списка команд."

    def _help(self) -> str:
        return (
            "Доступные команды:\n"
            "1. register --username <str> --password <str> — регистрация пользователя\n"
            "2. login --username <str> --password <str> — вход в систему\n"
            "3. deposit --amount <float> — пополнить баланс USD\n"
            "4. show-portfolio [--base <str>] — показать портфель и итог в базовой валюте (по умолчанию в USD)\n"
            "5. buy --currency <str> --amount <float> — купить валюту\n"
            "6. sell --currency <str> --amount <float> — продать валюту\n"
            "7. get-rate --from <str> --to <str> — получить курс валюты\n"
            "8. list-currencies — показать доступные валюты\n"
            "EXIT, QUIT — выход из приложения\n"
            "HELP — показать справку доступных команд\n"
        )

    def _signup(self, args: list[str]) -> str:
        parser = _SilentArgumentParser(prog="register", add_help=False)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: register --username <str> --password <str>"

        sts, msg = UserService.signup(username=parsed.username, 
                                             password=parsed.password)
        return msg

    def _login(self, args: list[str]) -> str:
        parser = _SilentArgumentParser(prog="login", add_help=False)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
    
        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: login --username <str> --password <str>"

        sts, msg, user_id = UserService.login(username=parsed.username,
                                                     password=parsed.password
                                                     )
        if sts:
            self.current_user = user_id
        
        return msg

    def _show_portfolio(self, args: list[str]) -> str:
        if self.current_user is None:
            return "Сначала выполните login"
        
        parser = _SilentArgumentParser(prog="show-portfolio", add_help=False)
        parser.add_argument("--base", required=False, default="USD")

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: show-portfolio [--base <str>]"

        try:
            sts, msg, portfolio = PortfolioService.get_portfolio(user_id=self.current_user,
                                                                 base=parsed.base
                                                                 )
            return msg
        except CurrencyNotFoundError as e:
            return f"{e}. Используйте 'list-currencies' для просмотра доступных валют."
        except ApiRequestError as e:
            return f"{e} Пожалуйста, повторите позже или проверьте сеть."

    def _buy(self, args: list[str]) -> str:
        if self.current_user is None:
            return "Сначала выполните login"
        
        parser = _SilentArgumentParser(prog="buy", add_help=False)
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True)

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: buy --currency <str> --amount <float>"

        currency = parsed.currency.upper()
        
        if currency == "USD":
            return "Ошибка: покупать USD через buy нельзя. Используйте deposit для пополнения."
        
        try:
            sts, msg = PortfolioService.buy(
                user_id=self.current_user,
                currency=currency,
                amount=parsed.amount,
            )
            return msg
        except ValueError as e:
            return str(e)
        except CurrencyNotFoundError as e:
            return f"{e}. Используйте 'list-currencies' для просмотра доступных валют."
        except ApiRequestError as e:
            return f"{e} Пожалуйста, повторите позже или проверьте сеть."
        except InsufficientFundsError as e:
            return str(e)

    def _sell(self, args: list[str]) -> str:
        if self.current_user is None:
            return "Сначала выполните login"
        
        parser = _SilentArgumentParser(prog="sell", add_help=False)
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True)

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: sell --currency <str> --amount <float>"

        currency = parsed.currency.upper()
        
        if currency == "USD":
            return "Ошибка: продавать USD нельзя."

        try:
            sts, msg = PortfolioService.sell(
                user_id=self.current_user, currency=currency, amount=parsed.amount
            )
            return msg
        except CurrencyNotFoundError as e:
            return f"{e}. Используйте 'list-currencies' для просмотра доступных валют."
        except ApiRequestError as e:
            return f"{e} Пожалуйста, повторите позже или проверьте сеть."
        except InsufficientFundsError as e:
            return str(e)
        except ValueError as e:
            return str(e)

    def _deposit(self, args: list[str]) -> str:
        """Пополняет USD баланс пользователя."""
        if self.current_user is None:
            return "Сначала выполните login"
        
        parser = _SilentArgumentParser(prog="deposit", add_help=False)
        parser.add_argument("--amount", required=True, type=float)

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: deposit --amount <float>"

        try:
            sts, msg = PortfolioService.deposit_usd(
                user_id=self.current_user,
                amount=parsed.amount
            )
            return msg
        except ValueError as e:
            return str(e)
        except InsufficientFundsError as e:
            return str(e)

    def _get_rate(self, args: list[str]) -> str:
        parser = _SilentArgumentParser(prog="get-rate", add_help=False)
        parser.add_argument("--from", dest="from_currency", required=True)
        parser.add_argument("--to", dest="to_currency", required=True)

        try:
            parsed = parser.parse_args(args)
        except (SystemExit, ValueError):
            return "Используйте: get-rate --from <str> --to <str>"

        try:
            sts, msg, rate, updated_at = get_rate(from_currency=parsed.from_currency, 
                                                  to_currency=parsed.to_currency)
            return msg
        except CurrencyNotFoundError as e:
            return f"{e}. Используйте 'list-currencies' для просмотра доступных валют."
        except ApiRequestError as e:
            return f"{e} Пожалуйста, повторите позже или проверьте сеть."
        
    def _list_currencies(self) -> str:
        currencies = sorted(_registried_currencies.values(), 
                           key=lambda c: c.code)
        lines = ["Доступные валюты:"]
        for currency in currencies:
            lines.append(f"  {currency.get_display_info()}")
        return "\n".join(lines)