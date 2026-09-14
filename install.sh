#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  for candidate in python3.11 python3.10 python3.12; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
if [[ -z "${PYTHON_BIN:-}" ]] || ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "未找到 Python 3.10–3.12。安装后重试，或执行：PYTHON_BIN=/path/to/python ./install.sh"
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
# CREPE 0.0.16 的构建脚本仍使用 pkg_resources，因此先安装兼容的 setuptools。
.venv/bin/pip install "setuptools<81" wheel "numpy<2"
.venv/bin/pip install --no-build-isolation -r requirements.txt

echo "安装完成。运行：./run.sh"
