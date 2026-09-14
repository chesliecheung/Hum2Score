#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "尚未创建虚拟环境。请先按 README.md 执行安装命令。"
  exit 1
fi

exec .venv/bin/python main.py
