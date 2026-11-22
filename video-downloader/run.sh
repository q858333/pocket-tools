#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8765}"
ROOT="$(pwd)"

pid=""
pid="$(lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
if [ -n "$pid" ]; then
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$cmd" == *"$ROOT"* && "$cmd" == *"uvicorn"* ]]; then
    echo "端口 $PORT 上已有本项目的旧服务 (PID $pid)，正在停止…"
    kill "$pid" 2>/dev/null || true
    sleep 1
  else
    echo "端口 $PORT 已被其他程序占用 (PID $pid)。"
    echo "请任选其一："
    echo "  1) 关闭占用端口的程序"
    echo "  2) 换端口启动: PORT=8766 ./run.sh"
    exit 1
  fi
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

export PYTHONPATH=.
echo "打开 http://127.0.0.1:$PORT"
exec uvicorn app.main:app --host 127.0.0.1 --port "$PORT"