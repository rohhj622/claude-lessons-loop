#!/bin/sh
# 훅용 파이썬 실행기. Windows(Git Bash)는 python, WSL 은 python3 인 경우가 많다.
# 사용: sh "${CLAUDE_PLUGIN_ROOT}/hooks/py.sh" <스크립트이름.py> [인자...]
DIR=$(dirname "$0")

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    exit 0  # 파이썬이 없으면 조용히 통과 (훅이 작업을 막지 않게)
fi

SCRIPT="$1"
shift
PYTHONIOENCODING=utf-8 exec "$PY" "$DIR/$SCRIPT" "$@"
