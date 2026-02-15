"""
Пользовательские исключения приложения%:
- InsufficientFundsError: возникает, когда недостаточно средств на кошельке.
- CurrencyNotFoundError: возникает, когда запрошена неизвестная валюта.
- ApiRequestError: возникает, когда возникает ошибка при обращении к внешним API.
"""


class InsufficientFundsError(Exception):
    """
    Выбрасывается, когда пользователь пытается снять больше денег чем на счёте.
    
    Attributes:
        available: Доступное количество
        required: Требуемое количество
        code: Код валюты
    """
    
    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        msg = (
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )        
        super().__init__(msg)


class CurrencyNotFoundError(Exception):
    """
    Выбрасывается, когда запрошена операция с неизвестной валютой.
    
    Attributes:
        code: Код неизвестной валюты
    """
    
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """
    Выбрасывается при ошибках при обращении к внешним API.
    
    Attributes:
        reason: Описание причины ошибки
    """
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")