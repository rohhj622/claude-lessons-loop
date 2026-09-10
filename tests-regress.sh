#!/bin/sh
# 회귀 시험. 따옴표 중첩으로 시험이 먼저 깨지는 일이 세 번 있어서 파일로 뺐다.
# 경로를 박아 두면 만든 사람 기계에서만 돈다. 실제로 그랬다 — 다른 기계에서는
# 첫 cd 에서 죽어서, 시험이 있다는 사실만 남고 아무것도 지키지 못했다.
R=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$R" || exit 1

# 시험 자산(볼트 사본·가짜 npm·입력 JSON 등)은 이 스크립트가 만들지 않는다.
# 자리를 환경변수로 받고, 없으면 어디를 봤는지 말하고 멈춘다. 자산 없이 돌면
# 거의 다 실패로 뜨는데, 그것은 코드가 깨진 것이 아니라 시험이 못 돈 것이다.
SP=${LESSONS_TEST_FIXTURES:-${TMPDIR:-/tmp}/claude-lessons-loop-fixtures}
if [ ! -d "$SP/vault" ]; then
  echo "시험 자산이 없다: $SP" >&2
  echo "LESSONS_TEST_FIXTURES=<자산 폴더> 로 자리를 알려 준다." >&2
  exit 2
fi

# 파이썬도 기계마다 이름과 자리가 다르다.
PY=${PY:-$(command -v python3 || command -v python)}
VENV_PY="$SP/venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY=$PY
export XDG_CONFIG_HOME="$SP/xdg" XDG_CACHE_HOME="$SP/xdgcache"
export QMD_INDEX="$SP/xdgcache/qmd/index.sqlite" LESSONS_VAULT="$SP/vault"

pass=0; fail=0
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
chk "회수 qmd"            "$(sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c 'qmd 의미검색')" "1"
chk "회수 기본검색기"      "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c '기본 검색기')" "1"
chk "무관 발화 침묵"       "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q2.json" | wc -l | tr -d ' ')" "0"
chk "점검기 MISSING 0"    "$(sh hooks/py.sh doctor.py | grep -c MISSING)" "0"
chk "미설정 안내"          "$(env LESSONS_VAULT= HOME="$SP/emptyhome" USERPROFILE="$SP/emptyhome" sh hooks/py.sh session-start.py | grep -c configure)" "1"
chk "파이썬 없음 안내"     "$(env PATH="$SP/nopy" sh hooks/py.sh session-start.py | grep -c '파이썬 3')" "1"
chk "파이썬 없음 침묵"     "$(env PATH="$SP/nopy" sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | wc -l | tr -d ' ')" "0"

chk "볼트 해석 환경변수"   "$(sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 해석 설정파일"   "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 없으면 코드1"    "$(env -u LESSONS_VAULT HOME="$SP/emptyhome" USERPROFILE="$SP/emptyhome" sh hooks/py.sh --quiet paths.py --vault >/dev/null 2>&1; echo $?)" "1"
chk "설정파일만으로 점검기" "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh doctor.py | sed -n 2p | grep -c OK)" "1"

# 최악 조건: 캐시 없음 + 느린 npm. 예전에는 여기서만 8초였다.
s=$(date +%s%N)
env PATH="$SP/slownpm" CLAUDE_PLUGIN_DATA="$SP/emptydata" $PY hooks/session-end.py < "$SP/qe.json"
e=$(date +%s%N)
ms=$(( (e-s)/1000000 ))
chk "SessionEnd 최악 100ms 이내 (${ms}ms)" "$([ "$ms" -lt 100 ] && echo yes || echo no)" "yes"

chk "import 이 qmd 안 찾음" "$(env PATH="$SP/slownpm" CLAUDE_PLUGIN_DATA="$SP/emptydata" $PY "$SP/importtime.py")" "yes"
chk "공백 경로 볼트"       "$(LESSONS_VAULT="$SP/공백 볼트" sh hooks/py.sh session-start.py | wc -l | tr -d ' ')" "3"
chk "claude validate"     "$(claude plugin validate .claude-plugin/plugin.json --strict >/dev/null 2>&1; echo $?)" "0"
chk "skills validate"     "$(claude plugin validate skills --strict >/dev/null 2>&1; echo $?)" "0"

echo
echo "통과 $pass · 실패 $fail"
[ "$fail" -eq 0 ]
