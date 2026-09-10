#!/usr/bin/env python
"""SessionStart 훅 — 상시 교훈을 컨텍스트에 주입한다.

이 훅은 검색을 쓰지 않는다. Lessons/INDEX.md 를 직접 읽는다. 그래서 검색 색인이
낡아 있어도 이쪽은 영향을 받지 않는다 — 색인 사고가 났을 때 마지막까지 남는 경로다.

대상은 INDEX.md 의 지정 묶음 안에서 중요도가 high 인 행뿐이다. 전부 넣으면 상시
컨텍스트를 통째로 먹는다.

전에는 셸 + awk 로 표를 읽었다. lesson-recall.py 가 같은 표를 정규식으로 또 읽어서
파서가 두 벌이었고, 둘 다 칸 **순서**에 묶여 있었다. 지금은 index_md.py 한 벌이
칸 **이름**으로 읽는다.

그리고 0건을 침묵으로 넘기지 않는다. 전에는 절 이름이 틀려도 머리글만 찍고 그
아래가 비었다. 사용자가 보는 것은 빈칸이었고 빈칸은 정상으로 읽힌다.

어떤 경우에도 exit 0 으로 끝난다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_md  # noqa: E402
from paths import VAULT, option  # noqa: E402

GROUP = option("index_group", "검증·판단 방법론")
IMPACT = "high"

UNCONFIGURED = ("claude-lessons-loop: 기록 폴더가 설정되지 않아 교훈 회수가 꺼져 "
                "있다. /claude-lessons-loop:configure 로 설정한다.")


def main():
    if not VAULT:
        # 설정을 안 한 사람의 작업을 막지 않는다. 다만 꺼져 있다는 사실은 알린다 —
        # 이 플러그인은 안 돌아도 화면이 똑같아서, 침묵하면 몇 주를 모르고 쓴다.
        print(UNCONFIGURED)
        return

    rows, problem = index_md.load(VAULT)
    if problem:
        print("상시 교훈을 못 읽었다 — " + problem)
        return

    groups = index_md.groups(rows)
    if GROUP not in groups:
        print("상시 교훈 묶음 '{}' 을 INDEX.md 에서 못 찾았다. "
              "있는 묶음: {}".format(GROUP, ", ".join(groups) or "(없음)"))
        return

    hits = [r for r in rows
            if r["group"] == GROUP and r.get("impact", "").lower() == IMPACT]
    if not hits:
        print("상시 교훈 묶음 '{}' 에 중요도 {} 인 행이 없다 "
              "(그 묶음의 행 {}건).".format(
                  GROUP, IMPACT, sum(1 for r in rows if r["group"] == GROUP)))
        return

    print("상시 교훈 — '{}' 묶음 중 중요도 {} "
          "(그 외 교훈은 발화마다 자동 회수됨):".format(GROUP, IMPACT))
    for r in hits:
        print("- [[{}]] {}".format(r["id"], r.get("title", "")))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        main()
    except Exception:
        pass  # 어떤 예외도 세션 시작을 막지 않는다
    sys.exit(0)
