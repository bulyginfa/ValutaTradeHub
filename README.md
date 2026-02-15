# ValutaTrade Hub

Платформа для симуляции торговли фиатными и криптовалютами. Проект предоставляет CLI-интерфейс для регистрации пользователей, управления портфелем, покупки/продажи валют и получением актуальных курсов из внешних источников.

## Ключевые возможности

- Регистрация и вход пользователей с хешированием паролей
- Портфели с валютными кошельками и базовой валютой USD
- Операции покупки/продажи валют с проверкой баланса
- Получение и кеширование курсов валют с TTL
- Обновление курсов из CoinGecko (криптовалюты) и ExchangeRate-API (фиатные валюты)
- Логирование доменных действий в JSON или человекочитаемом форматах

## Быстрый старт

### Требования

- Python 3.12+
- Poetry
- Доступ в интернет для обновления курсов

### Установка

```bash
poetry install
```

### Запуск CLI

```bash
poetry run project
```

При старте выводится приветствие и подсказка по командам. Для получения справки внутри CLI используйте команду `help`.

## Конфигурация

Основной конфиг хранится в [config.json](config.json). Его параметры доступны через `SettingsLoader` и используются для путей данных и логирования.

Пример ключевых параметров:

```json
{
	"data_dir": "data",
	"portfolios_file": "data/portfolios.json",
	"users_file": "data/users.json",
	"exchange_rates_file": "data/exchange_rates.json",
	"rates_file": "data/rates.json",
	"rates_ttl_seconds": 3600,
	"logs_dir": "logs",
	"log_file": "logs/actions.log",
	"log_level": "INFO",
	"log_format": "json"
}
```

Дополнительно можно указать путь к конфигурации в [pyproject.toml](pyproject.toml) через секцию `[tool.valutatrade]`:

```toml
[tool.valutatrade]
config_file = "config.json"
```

## Переменные окружения

Для ExchangeRate-API требуется ключ доступа. Создайте файл `.env` в корне проекта:

```bash
EXCHANGERATE_API_KEY=ваш_ключ
```

Загрузка `.env` выполняется автоматически при запуске CLI и при обращении к парсеру курсов.

## Использование CLI

### Основные команды

```text
register --username <str> --password <str>
login --username <str> --password <str>
deposit --amount <float>
show-portfolio [--base <str>]
buy --currency <str> --amount <float>
sell --currency <str> --amount <float>
get-rate --from <str> --to <str>
list-currencies
update-rates [--source coingecko|exchangerate]
show-rates [--currency <str>] [--top <int>] [--base <str>]
exit | quit
```

### Примеры

```text
register --username alice --password mypass
login --username alice --password mypass
deposit --amount 1000
buy --currency BTC --amount 0.01
show-portfolio --base USD
get-rate --from EUR --to USD
update-rates --source coingecko
show-rates --top 3 --base USD
```

## Обновление курсов

Курсы хранятся в локальном кеше и считаются актуальными в пределах `rates_ttl_seconds` (по умолчанию 3600 секунд). При обращении к курсу система использует кеш и при необходимости обновляет данные через парсер.

Источники:

- CoinGecko для криптовалют (BTC, ETH, SOL)
- ExchangeRate-API для фиатных валют (EUR, GBP, RUB, JPY, CNY)

## Логирование

Логи действий пишутся в файл `logs/actions.log` и/или в консоль. Доступны два формата:

- `json` — структурированные записи для парсинга
- `human` — удобный человекочитаемый формат

Формат и уровень задаются в [config.json](config.json). Логи ротируются по времени (ежедневно). Логируемые действия: REGISTER, LOGIN, BUY, SELL, DEPOSIT.

## Хранение данных

Проект использует JSON-хранилища, расположенные в директории `data/`:

- `users.json` — пользователи
- `portfolios.json` — портфели и кошельки
- `rates.json` — актуальные курсы
- `exchange_rates.json` — история обновлений курсов

## Архитектура

- `core/` — бизнес-логика, модели и доменные сервисы
- `infra/` — доступ к настройкам и хранилищу JSON
- `parser_service/` — обновление и кеширование курсов валют
- `cli/` — интерфейс командной строки

## Структура проекта

```text
valutatrade_hub/
	cli/                # CLI-интерфейс
	core/               # доменные модели и use-cases
	infra/              # настройки и JSON-хранилище
	parser_service/     # загрузка и кеш курсов
	logging_config.py   # конфигурация логирования
main.py               # точка входа CLI
config.json           # конфигурация приложения
data/                 # JSON данные
logs/                 # логи
```

## Команды Makefile

```bash
make install      # установка зависимостей через Poetry
make project      # запуск CLI
make lint         # статическая проверка ruff
```

## Демо

[Демонстрация работы приложения](https://asciinema.org/a/QcsS7K0Mx2RQvrw4)