#!/usr/bin/env bash
# WalletInfo — Ubuntu и macOS
# Developer: TG: @TanukiCode / Site: Tanuki.host
# Telegram: https://t.me/TanukiCode
# Site: https://tanuki.host
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PIP_DISABLE_PIP_VERSION_CHECK=1

if [[ $# -lt 1 ]]; then
  echo "Использование: ./info.sh <private_key_hex> [доп. аргументы info.py]" >&2
  echo "Пример: ./info.sh 0xYOUR_KEY" >&2
  exit 1
fi

pick_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

if ! PYTHON_BIN="$(pick_python)"; then
  echo "Не найден Python 3.10+." >&2
  echo "Ubuntu: sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip ca-certificates" >&2
  echo "macOS: brew install python@3.12" >&2
  exit 1
fi

if [[ ! -x "$ROOT/venv/bin/python" ]]; then
  echo "Создаю venv ($PYTHON_BIN)..." >&2
  rm -rf "$ROOT/venv"
  if ! "$PYTHON_BIN" -m venv "$ROOT/venv"; then
    echo "Не удалось создать venv." >&2
    echo "Ubuntu: sudo apt-get install -y python3-venv python3-pip ca-certificates" >&2
    echo "macOS: brew install python@3.12 ca-certificates" >&2
    exit 1
  fi
fi

PY="$ROOT/venv/bin/python"
if ! "$PY" -m pip install --timeout 60 -r "$ROOT/requirements.txt"; then
  echo "Не удалось поставить зависимости. Проверьте интернет и повторите запуск." >&2
  exit 1
fi

exec "$PY" "$ROOT/info.py" "$@"
