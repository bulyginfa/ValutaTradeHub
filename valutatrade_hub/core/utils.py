import json
from pathlib import Path

# core/validators.py
import re


def normalize_currency(code: str) -> str:
    """
    Валидация кода валюты.
    Формат:
    - 2–10 символов
    - только латиница и цифры
    - начинается с буквы
    """
    if code is None:
        raise ValueError("Код валюты должен быть непустой строкой.")

    code = str(code).strip().upper()

    if not code:
        raise ValueError("Код валюты должен быть непустой строкой.")

    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", code):
        raise ValueError("Некорректный код валюты 'currency'")

    return code

def validate_amount(amount: float) -> float:
        if not isinstance(amount, (int, float)):
            raise ValueError("Сумма должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма должна быть положительным числом.")
        return float(amount)

def load_exchange_rate(from_currency: str, to_currency: str) -> float:
    normalize_currency(from_currency)
    normalize_currency(to_currency)
    
    if from_currency == to_currency:
        return 1.0

    path = Path("data/rates.json")

    if not path.exists():
        raise FileNotFoundError("Файл с курсами валют не найден.")

    with path.open("r", encoding="utf-8") as f:
        rates_data = json.load(f)

    pair_key = f"{from_currency}_{to_currency}"

    if pair_key not in rates_data:
        raise ValueError(f"Курс для пары {pair_key} не найден.")

    return float(rates_data[pair_key]["rate"])