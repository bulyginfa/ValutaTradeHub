import argparse
import shlex
from typing import Optional

from ..core.usecases import UserService, PortfolioService


class CLIInterface:
    def __init__(self) -> None:
        self.current_user: Optional[int] = None

    def process_command(self, command_string: str) -> str:
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
        if command == "get-rate":
            return self._get_rate(tail)

        return f"Неизвестная команда: {command}. Введите 'help' для списка команд."

    def _help(self) -> str:
        return (
            "Доступные команды:"
            "\n"
            "0. help — показать эту справку\n"
            "   Использование: help\n\n"
            "1. register — регистрация пользователя\n"
            "   Использование: register --username <str> --password <str>\n\n"
            "2. login — вход в систему\n"
            "   Использование: login --username <str> --password <str>\n\n"
            "3. show-portfolio — показать портфель и итог в базовой валюте"
            "(по умолчанию в USD)\n"
            "   Использование: show-portfolio [--base <str>]\n\n"
            "4. buy — купить валюту\n"
            "   Использование: buy --currency <str> --amount <float>\n\n"
            "5. sell — продать валюту\n"
            "   Использование: sell --currency <str> --amount <float>\n\n"
            "6. get-rate — получить курс валюты\n"
            "   Использование: get-rate --from <str> --to <str>\n\n"
            "7. exit, quit — выход из приложения"
        )

    def _signup(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="register", add_help=False)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: register --username <str> --password <str>"

        status, message = UserService.signup(username=parsed.username, password=parsed.password)
        return message

    def _login(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="login", add_help=False)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
    
        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: login --username <str> --password <str>"

        status, message, user_id = UserService.login(username=parsed.username,
                                             password=parsed.password
                                             )
        if status == True:
            self.current_user = user_id
        
        return message

    def _show_portfolio(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="show-portfolio", add_help=False)
        parser.add_argument("--base", required=False, default="USD")

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: show-portfolio [--base <str>]"

        if self.current_user is None:
            return "Сначала выполните login"

        status, message = PortfolioService.show_portfolio(user_id=self.current_user,
                                                      base=parsed.base
                                                      )
        return message

    def _buy(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="buy", add_help=False)
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True)

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: buy --currency <str> --amount <float>"

        if self.current_user is None:
            return "Сначала выполните login"

        amount = float(parsed.amount)
        
        status, message = PortfolioService.buy(user_id=self.current_user,currency=parsed.currency, amount=amount )

        return message

    def _sell(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="sell", add_help=False)
        parser.add_argument("--currency", required=True)
        parser.add_argument("--amount", required=True)

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: sell --currency <str> --amount <float>"

        if self.current_user is None:
            return "Сначала выполните login"

        try:
            amount = float(parsed.amount)
        except (TypeError, ValueError):
            return "'amount' должен быть числом (int или float)"

        status, message = PortfolioService.sell(user_id=self.current_user, currency=parsed.currency, amount=amount)
        return message

    def _get_rate(self, args: list[str]) -> str:
        parser = argparse.ArgumentParser(prog="get-rate", add_help=False)
        parser.add_argument("--from", dest="from_currency", required=True)
        parser.add_argument("--to", dest="to_currency", required=True)

        try:
            parsed = parser.parse_args(args)
        except SystemExit:
            return "Использование: get-rate --from <str> --to <str>"

        status, message = UserService.get_rate(from_currency=parsed.from_currency, to_currency=parsed.to_currency)
        return message