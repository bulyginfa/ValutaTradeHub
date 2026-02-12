from __future__ import annotations

from valutatrade_hub.cli.interface import CLIInterface

WELCOME_TEXT = """
========================================
        ValutaTrade Hub CLI
========================================
Введите 'HELP' для справки
Введите 'EXIT' или 'QUIT' для выхода
"""


def run_cli() -> None:
    cli = CLIInterface()

    print(WELCOME_TEXT.strip())

    while True:
        try:
            command = input("\n> ").strip()

            if not command:
                continue

            response = cli.process_command(command)

            if response == "exit":
                print("Работа завершена. До встречи!")
                break

            if response:
                print(response)

        except KeyboardInterrupt:
            print("\nПрерывание пользователем. Завершение работы.")
            break
        except EOFError:
            print("\nПоток ввода закрыт. Завершение работы.")
            break
        except Exception as exc:
            print(f"Произошла ошибка: {exc}")

def main() -> None:
    run_cli()