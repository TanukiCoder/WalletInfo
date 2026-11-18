# WalletInfo

Утилита для своего secp256k1-ключа: строит адреса в нескольких сетях и проверяет балансы через публичные RPC и API. В обычном режиме печатает адреса и только ненулевые балансы, с оценкой в USD.

## Разработчик

- Telegram: [@TanukiCode](https://t.me/TanukiCode)
- Сайт: [Tanuki.host](https://tanuki.host)

TG: @TanukiCode / Site: Tanuki.host

## Что проверяет

- EVM-сети: нативный баланс и токены USDT, USDC, DAI, WETH и сетевые обёртки (Ethereum, BNB Smart Chain, Polygon, Arbitrum, Optimism, Avalanche, Base и другие из списка в `info.py`)
- Bitcoin, Bitcoin Cash, Litecoin, Dogecoin, Dash
- Tron: TRX и TRC20
- Solana: SOL, USDT и USDC

Ключ остаётся на вашей машине. Запросы уходят только к публичным RPC и API, чтобы прочитать баланс уже выведенного адреса.

## Требования

- Python 3.10 или новее
- Доступ в интернет к публичным RPC

На Ubuntu, если `python3 -m venv` падает:

```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip ca-certificates
```

На macOS, если Python ещё не стоит: `brew install python@3.12`.

На Windows ставьте Python с [python.org](https://www.python.org/downloads/) и включите «Add python.exe to PATH». Сборку из Microsoft Store лучше не использовать: у неё часто нет рабочего `venv`.

## Запуск

Скрипт сам создаёт `venv` и ставит зависимости. Ключ в команду подставляйте свой.

Ubuntu и macOS:

```bash
./info.sh 0xYOUR_PRIVATE_KEY
./info.sh 0xYOUR_PRIVATE_KEY -j 8
./info.sh 0xYOUR_PRIVATE_KEY --json
```

Windows, из `cmd` в папке проекта:

```bat
info.bat 0xYOUR_PRIVATE_KEY
info.bat 0xYOUR_PRIVATE_KEY -j 8
info.bat 0xYOUR_PRIVATE_KEY --json
```

Если окружение уже собрано, на любой системе:

```bash
python info.py 0xYOUR_PRIVATE_KEY
```

На Windows это `py -3 info.py 0xYOUR_PRIVATE_KEY`.

## Аргументы

| Аргумент | Описание |
| --- | --- |
| `private_key` | 32 байта в hex, 64 символа, префикс `0x` необязателен |
| `-j`, `--jobs` | Сколько запросов к RPC и API выполнять параллельно. По умолчанию 12. На один хост одновременно уходит не больше 4 |
| `--json` | Только JSON с адресами, без проверки балансов |

Пример обычного вывода:

```text
evm: 0x...
tron: T...
solana: ...
bitcoin p2wpkh: bc1...
==========
ETH: 0.01 (25.00$)
USDT ERC20: 10 (10.00$)
```

Нулевые балансы не печатаются.

## Структура

- `info.sh` — запуск на Ubuntu и macOS
- `info.bat` — запуск на Windows
- `info.py` — вывод адресов и проверка балансов
- `requirements.txt` — зависимости Python

## Как устроена устойчивость

- Повтор запроса при обрыве, таймауте и ответах 429/5xx, с паузой между попытками
- Отдельный лимит на каждый RPC-хост, чтобы публичные ноды не резали весь прогон
- Один запрос к Tron на все TRC20-балансы, а не пачка одинаковых
- Сертификаты через `certifi`, чтобы проверка TLS не зависела от набора CA в системе
- Учитывается `HTTPS_PROXY`, если сервер ходит в интернет через прокси
- RIPEMD-160 считается даже там, где OpenSSL 3 убрал этот алгоритм из `hashlib` (частый случай на Ubuntu)
- Keccak берётся из `pycryptodome`, без отдельной системной библиотеки
- Консоль переводится в UTF-8, в том числе в `cmd` на Windows

Если сеть так и не ответила, строка баланса не печатается, а причина уходит в stderr. Отсутствие строки само по себе не доказывает нулевой баланс, если выше есть предупреждение.

## Ограничения

Оценка в USD берётся с CoinGecko; для стейблкоинов используется 1 USD. Это справочная цифра, не котировка для сделки. Контракт с адресом неверной длины пропускается, чтобы один кривой адрес не ронял запросы к сети.

Проверяйте только ключи, которыми вы владеете.
