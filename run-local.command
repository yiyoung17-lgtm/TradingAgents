#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -eq 0 ]]; then
    .venv/bin/python local_launch.py || { status=$?; read -r -p '按 Enter 关闭窗口…'; exit "$status"; }
else
    exec .venv/bin/python local_launch.py "$@"
fi
