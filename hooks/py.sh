#!/bin/sh
# 훅용 파이썬 실행기.
#
# 사용: sh "${CLAUDE_PLUGIN_ROOT}/hooks/py.sh" [--quiet] <스크립트.py> [인자...]
#
# 파이썬이 없으면 **한 줄을 내고** exit 0 한다. 작업은 막지 않되 침묵하지 않는다.
#
# 전에는 아무 말 없이 exit 0 했다. 실측(2026-09-10, 파이썬만 없는 PATH):
# 훅 넷과 점검기까지 전부 빈 출력에 종료코드 0. 실제 세션에서 모델이 받은 것도
# 없었고 stderr 도 비어 있었다. 설치돼 있고 훅도 유효한데 한마디 없이 아무 일도
# 안 하는 상태였다. 조용한 실패는 성공과 똑같이 생긴다 — 이 저장소의 첫 교훈이다.
#
# 기본은 말하는 쪽이다. 침묵이 필요한 곳에서만 --quiet 를 준다. 반대로 두면
# 나중에 추가하는 스크립트가 기본으로 조용히 죽는다.
# dirname 을 부르지 않는다. 이 스크립트는 PATH 가 망가진 곳에서도 한마디는
# 해야 하는데, 외부 명령을 쓰면 그 자리에서 같이 죽는다. 셸 내장으로 푼다.
case "$0" in */*) DIR=${0%/*} ;; *) DIR=. ;; esac

QUIET=0
if [ "$1" = "--quiet" ]; then
    QUIET=1
    shift
fi

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    if [ "$QUIET" = "0" ]; then
        echo "claude-lessons-loop: 파이썬 3 을 못 찾아 교훈 회수가 통째로 꺼져 있다."
        echo "  확인: python3 --version"
        echo "  없으면 설치하거나, 있는데 못 찾는 것이면 PATH 를 확인한다."
    fi
    exit 0   # 파이썬이 없다고 작업을 막지는 않는다
fi

SCRIPT="$1"
shift
PYTHONIOENCODING=utf-8 exec "$PY" "$DIR/$SCRIPT" "$@"
