#!/bin/sh
# 회귀 시험. 따옴표 중첩으로 시험이 먼저 깨지는 일이 세 번 있어서 파일로 뺐다.
R=/Users/babymac/Documents/0.codes/claude-lessons-loop
SP=/private/tmp/claude-501/-Users-babymac-Documents-0-codes-claude-lessons-loop/ac1d9c6c-dd65-48ed-a981-09c72a07461f/scratchpad
cd "$R" || exit 1
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

chk "파서 자가검사"       "$(python3 hooks/index_md.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "매니페스트 자가검사"  "$(python3 hooks/manifests.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "매니페스트 일치"      "$(python3 hooks/manifests.py >/dev/null 2>&1; echo $?)" "0"
chk "lint 자가검사"       "$(cd "$SP/vault" && python3 _Meta/lint.py --selftest >/dev/null 2>&1; echo $?)" "0"
chk "lint 정상"           "$(cd "$SP/vault" && python3 _Meta/lint.py >/dev/null 2>&1; echo $?)" "0"
chk "lint INDEX 없음"     "$(cd "$SP/v3" && python3 _Meta/lint.py >/dev/null 2>&1; echo $?)" "1"
chk "lint 칸이름"         "$(cd "$SP/v4" && python3 _Meta/lint.py >/dev/null 2>&1; echo $?)" "1"
chk "drift 자가검사"      "$(cd "$SP/vault" && "$SP/venv/bin/python" _Meta/drift.py 2>&1 | grep -c '자가검사 OK')" "1"

chk "상시 교훈"           "$(sh hooks/py.sh session-start.py | wc -l | tr -d ' ')" "3"
chk "회수 qmd"            "$(sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c 'qmd 의미검색')" "1"
chk "회수 기본검색기"      "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | grep -c '기본 검색기')" "1"
chk "무관 발화 침묵"       "$(QMD_BIN=/없음 sh hooks/py.sh --quiet lesson-recall.py < "$SP/q2.json" | wc -l | tr -d ' ')" "0"
chk "점검기 MISSING 0"    "$(sh hooks/py.sh doctor.py | grep -c MISSING)" "0"
chk "미설정 안내"          "$(LESSONS_VAULT= sh hooks/py.sh session-start.py | grep -c configure)" "1"
chk "파이썬 없음 안내"     "$(env PATH="$SP/nopy" sh hooks/py.sh session-start.py | grep -c '파이썬 3')" "1"
chk "파이썬 없음 침묵"     "$(env PATH="$SP/nopy" sh hooks/py.sh --quiet lesson-recall.py < "$SP/q.json" | wc -l | tr -d ' ')" "0"

chk "볼트 해석 환경변수"   "$(sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 해석 설정파일"   "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh --quiet paths.py --vault | grep -c vault)" "1"
chk "볼트 없으면 코드1"    "$(env -u LESSONS_VAULT sh hooks/py.sh --quiet paths.py --vault >/dev/null 2>&1; echo $?)" "1"
chk "설정파일만으로 점검기" "$(env -u LESSONS_VAULT CLAUDE_PLUGIN_DATA="$SP/plugindata" sh hooks/py.sh doctor.py | sed -n 2p | grep -c OK)" "1"

# 최악 조건: 캐시 없음 + 느린 npm. 예전에는 여기서만 8초였다.
s=$(date +%s%N)
env PATH="$SP/slownpm" CLAUDE_PLUGIN_DATA="$SP/emptydata" /usr/bin/python3 hooks/session-end.py < "$SP/qe.json"
e=$(date +%s%N)
ms=$(( (e-s)/1000000 ))
chk "SessionEnd 최악 100ms 이내 (${ms}ms)" "$([ "$ms" -lt 100 ] && echo yes || echo no)" "yes"

chk "import 이 qmd 안 찾음" "$(env PATH="$SP/slownpm" CLAUDE_PLUGIN_DATA="$SP/emptydata" /usr/bin/python3 "$SP/importtime.py")" "yes"
chk "공백 경로 볼트"       "$(LESSONS_VAULT="$SP/공백 볼트" sh hooks/py.sh session-start.py | wc -l | tr -d ' ')" "3"
chk "claude validate"     "$(claude plugin validate .claude-plugin/plugin.json --strict >/dev/null 2>&1; echo $?)" "0"
chk "skills validate"     "$(claude plugin validate skills --strict >/dev/null 2>&1; echo $?)" "0"

echo
echo "통과 $pass · 실패 $fail"
[ "$fail" -eq 0 ]
