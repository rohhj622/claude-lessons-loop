#!/bin/sh
# SessionStart: 상시 교훈을 컨텍스트에 주입한다.
#
# 이 훅은 검색을 쓰지 않는다. Lessons/INDEX.md 를 awk 로 직접 읽는다.
# 그래서 검색 색인이 낡아 있어도 이쪽은 영향을 받지 않는다 — 색인 사고가
# 났을 때 마지막까지 남는 경로가 여기다.
#
# 대상은 INDEX.md 의 GROUP 절 안에서 impact 가 high 인 행뿐이다.
# 전부 넣으면 상시 컨텍스트를 통째로 먹는다. 절 이름과 임계값은 아래 둘이다.

GROUP="검증·판단 방법론"

# LESSONS_VAULT 를 Windows 표기로 적어 뒀어도 WSL 에서 돌게 한다(그 반대도).
resolve() {
    for c in "$1" "$(echo "$1" | sed -E 's|^([A-Za-z]):|/mnt/\L\1|')"; do
        [ -d "$c" ] && echo "$c" && return
    done
}
VAULT=$(resolve "$LESSONS_VAULT")
[ -n "$VAULT" ] || exit 0
INDEX="$VAULT/Lessons/INDEX.md"
[ -f "$INDEX" ] || exit 0

{
    echo "상시 교훈 — '$GROUP' 묶음 중 impact:high (그 외 교훈은 발화마다 자동 회수됨):"
    awk -v g="^## $GROUP" '
        $0 ~ g      { f = 1; next }
        /^## /      { f = 0 }
        f && /^\| \[LSN/ {
            split($0, a, "|"); imp = a[4]; gsub(/ /, "", imp)
            if (imp == "high") print
        }
    ' "$INDEX"
} 2>/dev/null || true
