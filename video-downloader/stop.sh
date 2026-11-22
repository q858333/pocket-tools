#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8765}"
ROOT="$(pwd)"
stopped=0

while IFS= read -r pid; do
  [ -n "$pid" ] || continue
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$cmd" == *"$ROOT"* && "$cmd" == *"uvicorn"* ]]; then
    echo "停止本机服务 PID $pid（端口 $PORT）"
    kill "$pid" 2>/dev/null || true
    sleep 0.3
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    stopped=1
  fi
done < <(lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)

if [ "$stopped" -eq 0 ]; then
  if pkill -f "${ROOT}/.venv/bin/uvicorn app.main:app" 2>/dev/null; then
    echo "已停止 uvicorn"
    stopped=1
  fi
fi

if [ "$stopped" -eq 0 ]; then
  echo "未在端口 $PORT 发现本项目的运行中的服务"
else
  sleep 0.5
  if lsof -i TCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "端口仍被占用，可执行: lsof -i :$PORT"
    exit 1
  fi
  echo "已停止"
fi