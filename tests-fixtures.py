#!/usr/bin/env python
"""회귀 시험 자산을 만든다.

전에는 이 자산들이 만든 사람의 scratchpad 에 손으로 놓여 있었다. 그 세션이
끝나면서 통째로 사라졌고, 시험은 있는데 아무 기계에서도 못 도는 상태가 됐다.
그래서 자산을 코드로 옮긴다.

한글이 든 파일이 많다. 셸 heredoc 으로 만들면 환경에 따라 인코딩이 깨지므로
파이썬에서 utf-8 을 명시해 쓴다.

  python tests-fixtures.py <자산 폴더>

이미 있으면 지우고 다시 만든다. 시험 자산은 늘 같은 상태여야 한다.
"""
import io
import os
import shutil
import stat
import sys

# Windows 콘솔의 기본 코드페이지는 한글을 못 낸다. 자산 생성기가 거기서 죽으면
# 시험이 시작도 못 한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "templates", "vault")


def write(path, text, executable=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP)


# 상시 교훈 시험은 "여러 건이 다 나오는가"를 본다. 템플릿에는 high 가 한 건뿐이라
# 한 건 더 심는다. 스키마를 지켜야 lint 시험이 같이 통과한다.
EXTRA_ID = "LSN-2026-01-01-002"
EXTRA_TITLE = "빈 결과와 못 재고 있는 것을 구분한다"
EXTRA_NOTE = """---
type: lesson
id: {id}
aliases: ["{title}"]
name: "{title}"
impact: high
date: 2026-01-01
tags: [lesson, 검증]
author: "[[Claude]]"
---

# {title}

## 상황

시험 자산으로 심은 교훈이다. 회수 훅이 여러 건을 다 내보내는지 본다.

## 실수 내용

한 건만 나오는 것을 정상으로 읽었다.

## 원인

기대 건수를 정해 두지 않아서 줄어든 것을 알아채지 못했다.

## 앞으로 할 것 · 하지 말 것

- 목록을 내보내는 코드는 건수까지 시험한다.
""".format(id=EXTRA_ID, title=EXTRA_TITLE)

EXTRA_ROW = "| [{id}]({id}.md) | {title} | high | 2026-01-01 |\n".format(
    id=EXTRA_ID, title=EXTRA_TITLE)


def make_vault(dest, extra=True):
    shutil.copytree(TEMPLATE, dest)
    if not extra:
        return dest
    write(os.path.join(dest, "Lessons", EXTRA_ID + ".md"), EXTRA_NOTE)
    idx = os.path.join(dest, "Lessons", "INDEX.md")
    with io.open(idx, encoding="utf-8") as f:
        lines = f.readlines()
    # 첫 표의 마지막 행 바로 뒤에 넣는다. 표를 찾는 규칙은 index_md.py 와 같다.
    out, put = [], False
    for i, ln in enumerate(lines):
        out.append(ln)
        if not put and ln.startswith("| [LSN-"):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.startswith("| ["):
                out.append(EXTRA_ROW)
                put = True
    assert put, "INDEX.md 에서 교훈 행을 못 찾았다"
    write(idx, "".join(out))
    return dest


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    sp = os.path.abspath(sys.argv[1])
    if os.path.isdir(sp):
        shutil.rmtree(sp)
    os.makedirs(sp)

    make_vault(os.path.join(sp, "vault"))
    make_vault(os.path.join(sp, "공백 볼트"))

    # INDEX.md 가 없는 볼트. lint 는 이것을 도구 실패로 보고해야 한다.
    v3 = make_vault(os.path.join(sp, "v3"), extra=False)
    os.remove(os.path.join(v3, "Lessons", "INDEX.md"))

    # 표 머리글의 칸 이름을 바꾼 볼트. 훅이 표를 못 읽는 상태다.
    v4 = make_vault(os.path.join(sp, "v4"), extra=False)
    idx4 = os.path.join(v4, "Lessons", "INDEX.md")
    with io.open(idx4, encoding="utf-8") as f:
        body = f.read()
    write(idx4, body.replace("| ID | 제목 | 중요도 | 날짜 |",
                             "| 번호 | 이름 | 등급 | 일자 |"))

    # 훅 입력. prompt 는 MIN_PROMPT(12자)를 넘어야 회수가 돈다.
    # 기본 검색기는 글자 겹침으로 점수를 낸다. 교훈 제목과 겹치는 말이 없으면
    # 점수 미달로 아무것도 안 붙고, 그것은 검색 경로가 깨진 것과 구분이 안 된다.
    write(os.path.join(sp, "q.json"),
          '{"prompt": "없다고 결론짓기 전에 양성 대조를 어떻게 하면 되지"}\n')
    write(os.path.join(sp, "q2.json"),
          '{"prompt": "오늘 점심에 김치찌개를 먹을까 순두부를 먹을까"}\n')
    write(os.path.join(sp, "qe.json"), '{"reason": "clear"}\n')

    # 설정 파일만으로 볼트가 풀리는지 보는 자리.
    write(os.path.join(sp, "plugindata", "config.json"),
          '{"vault_dir": "%s/vault"}\n' % sp.replace("\\", "/"))

    for empty in ("nopy", "emptydata", "emptyhome", "xdg", "xdgcache"):
        os.makedirs(os.path.join(sp, empty), exist_ok=True)

    # 느린 npm. `npm root -g` 를 부르면 상한에 걸리도록 오래 끈다.
    write(os.path.join(sp, "slownpm", "npm"), "#!/bin/sh\nsleep 30\n", True)

    # import 만으로 npm 조회가 일어나면 훅이 매 발화 느려진다. 조회는 qmd()
    # 를 실제로 부를 때만 일어나야 한다. subprocess 를 막아 두고 확인한다.
    write(os.path.join(sp, "importtime.py"), '''import subprocess, sys, os
sys.path.insert(0, os.path.join(%r, "hooks"))
called = []
subprocess.run = lambda *a, **k: called.append(a)
subprocess.check_output = lambda *a, **k: called.append(a)
import paths  # noqa: F401
print("no" if called else "yes")
''' % HERE)

    # SessionEnd 시간 측정. **벽시계 절대값을 쓰지 않는다.** 파이썬 인터프리터
    # 시작만으로 중앙값 76ms·최악 307ms 가 나오는 기계가 있다(2026-09-11,
    # Windows 실측 30회). 절대 상한 100ms 는 훅 코드가 0ms 여도 그런 기계에서
    # 그냥 깨지고, 깨진 채로 방치되면 진짜 회귀까지 같이 묻힌다.
    #
    # 그래서 같은 조건에서 빈 인터프리터를 함께 재고 그 차이만 본다. 기계
    # 성능과 그때그때의 부하는 양쪽에 똑같이 실리므로 차감된다. 부하 잡음은
    # 위로만 실리므로 평균이 아니라 최솟값을 쓴다.
    write(os.path.join(sp, "timing.py"), '''"""훅이 빈 인터프리터에 더하는 몫(ms)을 잰다. 환경은 부모에게서 상속받는다."""
import subprocess, sys, os, time

HOOK = os.path.join(%r, "hooks", "session-end.py")
STDIN = sys.argv[1]
N = 5


def best(argv, stdin):
    lo = None
    for _ in range(N):
        with open(stdin, "rb") as f:
            t = time.perf_counter()
            subprocess.run([sys.executable] + argv, stdin=f,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ms = (time.perf_counter() - t) * 1000
        lo = ms if lo is None else min(lo, ms)
    return lo


null = os.devnull
floor = best(["-c", "pass"], null)
hook = best([HOOK], STDIN)
print("%%d %%d %%d" %% (round(hook - floor), round(floor), round(hook)))
''' % HERE)

    print("자산을 만들었다: " + sp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
