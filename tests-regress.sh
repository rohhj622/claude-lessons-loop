#!/bin/sh
# 회귀 시험. 따옴표 중첩으로 시험이 먼저 깨지는 일이 세 번 있어서 파일로 뺐다.
# 경로를 박아 두면 만든 사람 기계에서만 돈다. 실제로 그랬다 — 다른 기계에서는
# 첫 cd 에서 죽어서, 시험이 있다는 사실만 남고 아무것도 지키지 못했다.
R=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$R" || exit 1

# 파이썬도 기계마다 이름과 자리가 다르다.
PY=${PY:-$(command -v python3 || command -v python)}
[ -n "$PY" ] || { echo "파이썬이 없다." >&2; exit 2; }

# Windows 콘솔의 기본 코드페이지는 한글을 못 낸다. 이것 없이는 한글을 찍는
# 검사가 코드 문제와 무관하게 UnicodeEncodeError 로 죽는다.
export PYTHONIOENCODING=utf-8

# 자산은 시험이 직접 만든다. 전에는 만든 사람의 임시 폴더에 손으로 놓여 있었고,
# 그 세션이 끝나면서 사라져 아무 기계에서도 못 도는 시험이 됐다.
# 이 폴더는 시험 소유다 — 매번 지우고 다시 만든다.
SP=${LESSONS_TEST_FIXTURES:-${TMPDIR:-/tmp}/claude-lessons-loop-fixtures}
"$PY" tests-fixtures.py "$SP" >/dev/null || {
  echo "시험 자산을 만들지 못했다: $SP" >&2; exit 2; }

VENV_PY=$PY
export XDG_CONFIG_HOME="$SP/xdg" XDG_CACHE_HOME="$SP/xdgcache"
export QMD_INDEX="$SP/xdgcache/qmd/index.sqlite" LESSONS_VAULT="$SP/vault"

pass=0; fail=0; skip=0
skp() {
  echo "건너뜀 $1 ($2)"; skip=$((skip+1))
}
chk() {
  if [ "$2" = "$3" ]; then
    echo "OK   $1"; pass=$((pass+1))
  else
    echo "실패 $1 (기대 $3, 실제 $2)"; fail=$((fail+1))
  fi
}

chk "파서 자가검사"       "$($PY hooks/index_md.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "매니페스트 자가검사"  "$($PY hooks/manifests.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "매니페스트 일치"      "$($PY hooks/manifests.py >/dev/null 2>&1; echo $?)" "0"
chk "lint 자가검사"       "$(cd "$SP/vault" && $PY _Meta/lint.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "lint 정상"           "$(cd "$SP/vault" && $PY _Meta/lint.py >/dev/null 2>&1; echo $?)" "0"
chk "lint INDEX 없음"     "$(cd "$SP/v3" && $PY _Meta/lint.py >/dev/null 2>&1; echo $?)" "1"
chk "lint 칸이름"         "$(cd "$SP/v4" && $PY _Meta/lint.py >/dev/null 2>&1; echo $?)" "1"
chk "drift 자가검사"      "$(cd "$SP/vault" && "$VENV_PY" _Meta/drift.py 2>&1 | grep -c '자가검사 OK')" "1"

chk "상시 교훈"           "$(sh hooks/py.sh session-start.py | wc -l | tr -d ' ')" "3"
# qmd 색인은 시험이 만들 수 없다 — 첫 색인에서 모델 2 GB 를 내려받는다.
# 없으면 건너뛴다. 조용히 통과시키면 검색 경로가 깨져도 모른다.
if [ -f "$QMD_INDEX" ]; then
  chk "회수 qmd"          "$(sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c 'qmd 의미검색')" "1"
else
  skp "회수 qmd" "qmd 색인이 없다"
fi
chk "회수 기본검색기"      "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c '기본 검색기')" "1"
# 제목 말로 물으면 제목 가중치(0.7)가 실려 0.5 를 넘어야 한다. 본문의 H1 만으로
# 잡히면 0.15 — 하한(0.12) 바로 위라, 건수만 세면 이 회귀는 통과해 버린다.
chk "회수 title 가중치"     "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q3.json" | grep 'LSN-2026-01-01-003' | sed 's/.*관련도 \([0-9.]*\).*/\1/' | awk '{print ($1 >= 0.5) ? "yes" : "no"}')" "yes"
chk "현황 발화에 실측 의무"   "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q4.json" | grep -c '⚑')" "1"
chk "짧은 현황 발화에도 실측 의무" "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q5.json" | grep -c '⚑')" "1"
# 검색기가 예외를 던져도 문구는 나가야 한다. 훅 트리 사본에서 search.py 만 깨뒀다.
chk "검색 실패해도 실측 의무"  "$(QMD_BIN=/없음 sh "$SP/brokenhooks/py.sh" --quiet lesson-recall.py < "$SP/q4.json" | grep -c '⚑')" "1"
chk "live_gate 끄면 침묵"    "$(CLAUDE_PLUGIN_OPTION_LIVE_GATE=false QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q4.json" | grep -c '⚑')" "0"
chk "무관 발화 침묵"     "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q2.json" | wc -l | tr -d ' ')" "0"
if [ -f "$QMD_INDEX" ]; then
  chk "점검기 MISSING 0"  "$(sh hooks/py.sh doctor.py | grep -c MISSING)" "0"
else
  skp "점검기 MISSING 0" "qmd 색인이 없다"
fi
chk "미설정 안내"          "$(env LESSONS_VAULT= HOME="$SP/emptyhome" USERPROFILE="$SP/emptyhome" sh hooks/py.sh session-start.py | grep -c configure)" "1"
chk "파이썬 없음 안내"     "$(env PATH="$SP/nopy" /bin/sh hooks/py.sh session-start.py | grep -c '파이썬 3')" "1"
chk "파이썬 없음 침묵"     "$(env PATH="$SP/nopy" /bin/sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | wc -l | tr -d ' ')" "0"

chk "볼트 해석 환경변수"   "$(sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 해석 설정파일"   "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 없으면 코드1"    "$(env -u LESSONS_VAULT HOME="$SP/emptyhome" USERPROFILE="$SP/emptyhome" sh hooks/py.sh --quiet paths.py --vault >/dev/null 2>&1; echo $?)" "1"
# 어느 사본이 도는지 가르는 두 행. 버전은 매니페스트 값과 같아야 하고 해시는 12자 16진수.
chk "점검기 버전 행"        "$(sh hooks/py.sh doctor.py | grep '플러그인 버전' | grep -c "$(grep -o '"version": *"[^"]*"' .claude-plugin/plugin.json | sed 's/.*"\([^"]*\)"$/\1/')")" "1"
chk "점검기 해시 행"        "$(sh hooks/py.sh doctor.py | grep '설치본 해시' | grep -Ec '[0-9a-f]{12}$')" "1"
chk "설정파일만으로 점검기" "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh doctor.py | sed -n 2p | grep -c OK)" "1"

# 최악 조건: 캐시 없음 + 느린 npm. 예전에는 여기서만 8초였다.
#
# 재는 것은 훅의 벽시계 시간이 아니라 **빈 인터프리터에 훅이 더하는 몫**이다.
# 절대 상한 100ms 를 쓰던 동안 이 검사는 기계에 따라 경계에서 진동했는데,
# 실측해 보니 인터프리터 시작만으로 76ms 를 쓰는 기계가 있었다(2026-09-11,
# Windows 30회). 훅이 통제하지 못하는 것을 상한에 넣고 있었던 셈이다.
#
# 상한 300ms 는 넉넉하다. 이 검사가 잡으려는 회귀는 `import 만으로 qmd 탐색`
# 같은 자릿수가 다른 사고이지, 50ms 와 100ms 의 차이가 아니다. 좁게 잡아
# 진동시키면 실패를 사람이 넘기게 되고 그 순간 진짜 회귀까지 같이 묻힌다.
# **HOME 도 함께 돌린다.** 이것 없이는 최악 조건이 성립하지 않는다. qmd 가
# 깔린 기계에서는 `~/AppData/Roaming/npm/...` 이 표준 후보에 걸려서, 느린 npm
# 을 부를 일 자체가 없다. 실제로 그 자산은 한 번도 안 불리고 있었다(2026-09-11).
rm -rf "$SP/perfdata" "$SP/npmcalled"
t=$(env PATH="$SP/slownpm" LESSONS_TEST_DATA="$SP/perfdata"       HOME="$SP/emptyhome" USERPROFILE="$SP/emptyhome"       $PY "$SP/timing.py" "$SP/qe.json")
delta=${t%% *}
chk "SessionEnd 추가 비용 300ms 이내 (${t}ms · 몫/바닥/전체)"     "$([ "$delta" -lt 300 ] && echo yes || echo no)" "yes"

# 위 검사의 양성 대조. 느린 npm 이 정말 불렸는지를 센다. 안 불렸다면 위 숫자는
# 최악 조건이 아니라 아무것도 없는 경로를 잰 것이고, 그러면 훅이 느려져도 안
# 걸린다. 재색인은 분리된 자식이 하므로 흔적이 조금 늦게 생긴다 — 잠깐 기다린다.
i=0
while [ "$i" -lt 30 ] && [ ! -f "$SP/npmcalled" ]; do
  sleep 0.1; i=$((i+1))
done
# Lessons/ 는 색인보다 낡고 Projects/ 노트만 새롭다. 훅은 재색인을 띄워야 한다.
# 부모가 남기는 줄을 본다 — 분리된 자식은 qmd 가 없어 "건너뜀" 을 뒤에 덧붙인다.
# 로그는 누적이라 앞선 시험 줄이 섞인다. 이번 실행이 더한 줄만 본다.
n=$(wc -l < hooks/session-end.log 2>/dev/null || echo 0)
LESSONS_VAULT="$SP/vaultproj" QMD_INDEX="$SP/fakeidx" QMD_BIN=/없음 sh hooks/py.sh --quiet session-end.py < "$SP/qe.json"
chk "Projects 변경도 재색인"  "$(tail -n +$((n+1)) hooks/session-end.log | grep -c '재색인을 분리해 띄웠다')" "1"
# 색인이 볼트 전체보다 새로우면 건너뛴다. 순회 상한에 걸린 경우에만 갈라진다.
n=$(wc -l < hooks/session-end.log 2>/dev/null || echo 0)
LESSONS_VAULT="$SP/vault" QMD_INDEX="$SP/fakeidx2" QMD_BIN=/없음 sh hooks/py.sh --quiet session-end.py < "$SP/qe.json"
chk "색인이 최신이면 건너뜀"  "$(tail -n +$((n+1)) hooks/session-end.log | grep -c '건너뜀 — 색인이 최신')" "1"
n=$(wc -l < hooks/session-end.log 2>/dev/null || echo 0)
LESSONS_WALK_BUDGET=0 LESSONS_VAULT="$SP/vault" QMD_INDEX="$SP/fakeidx2" QMD_BIN=/없음 sh hooks/py.sh --quiet session-end.py < "$SP/qe.json"
chk "순회 상한이면 재색인"    "$(tail -n +$((n+1)) hooks/session-end.log | grep -c '상한에 걸림')" "1"
chk "느린 npm 이 실제로 불렸다" "$([ -f "$SP/npmcalled" ] && echo yes || echo no)" "yes"

chk "import 이 qmd 안 찾음" "$(env PATH="$SP/slownpm" CLAUDE_PLUGIN_DATA="$SP/emptydata" $PY "$SP/importtime.py")" "yes"
chk "공백 경로 볼트"       "$(LESSONS_VAULT="$SP/공백 볼트" sh hooks/py.sh session-start.py | wc -l | tr -d ' ')" "3"
chk "claude validate"     "$(claude plugin validate .claude-plugin/plugin.json --strict >/dev/null 2>&1; echo $?)" "0"
chk "skills validate"     "$(claude plugin validate skills --strict >/dev/null 2>&1; echo $?)" "0"

echo
echo "통과 $pass · 실패 $fail · 건너뜀 $skip"
[ "$fail" -eq 0 ]
