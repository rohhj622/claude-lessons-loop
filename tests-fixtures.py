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
import time

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

# 제목을 `title` 로만 적은 교훈. 실제 볼트의 스키마가 그렇다(name 이 없다).
# 기본 검색기가 `title` 을 제목 가중 필드로 안 읽던 회귀를 잡는다 — 본문에는
# 제목의 말이 하나도 없어서, 제목을 못 읽으면 점수가 0 이 된다.
TITLE_ID = "LSN-2026-01-01-003"
TITLE_TITLE = "임시 창구가 닫히면 답신 주소를 잃는다"
TITLE_NOTE = """---
type: lesson
id: {id}
title: "{title}"
impact: medium
date: 2026-01-01
tags: [lesson, 검증]
author: "[[Claude]]"
---

# {title}

## 상황

시험 자산으로 심은 교훈이다. 프론트매터에 name 이 없고 title 만 있다.

## 실수 내용

본문에서 제목 낱말이 나오는 자리는 위 H1 하나뿐이다. 본문만 읽으면 0.15,
제목까지 읽으면 0.5 를 넘는다. 그 차이로 검색기가 어디를 읽었는지 갈린다.

## 원인

머리글 필드 이름이 볼트마다 다른데 검색기는 한 가지만 알았다.

## 앞으로 할 것 · 하지 말 것

- 검색기가 읽는 필드 목록에 볼트 스키마의 것을 넣는다.
""".format(id=TITLE_ID, title=TITLE_TITLE)

TITLE_ROW = "| [{id}]({id}.md) | {title} | medium | 2026-01-01 |\n".format(
    id=TITLE_ID, title=TITLE_TITLE)


def make_vault(dest, extra=True):
    shutil.copytree(TEMPLATE, dest)
    if not extra:
        return dest
    write(os.path.join(dest, "Lessons", EXTRA_ID + ".md"), EXTRA_NOTE)
    write(os.path.join(dest, "Lessons", TITLE_ID + ".md"), TITLE_NOTE)
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
                out.append(TITLE_ROW)
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

    # Lessons/ 는 색인보다 낡고 Projects/ 의 노트만 색인보다 새로운 볼트.
    # 종료 훅이 Lessons/ 만 보면 "색인이 최신" 으로 건너뛰고, 그 노트는 다음
    # 세션 검색에서 통째로 빠진다(2026-09-14 GPT 검토가 짚음). 시각은 mtime 을
    # 직접 박는다 — 만든 순서에 기대면 같은 초 안에서 동률이 나 판정이 흔들린다.
    vp = make_vault(os.path.join(sp, "vaultproj"))
    now = time.time()
    for name in os.listdir(os.path.join(vp, "Lessons")):
        os.utime(os.path.join(vp, "Lessons", name), (now - 120, now - 120))
    os.utime(os.path.join(vp, "Lessons"), (now - 120, now - 120))
    write(os.path.join(sp, "fakeidx"), "")
    os.utime(os.path.join(sp, "fakeidx"), (now - 60, now - 60))
    note = os.path.join(vp, "Projects", "PRJ-2026-001.md")
    write(note, "---\ntype: project\n---\n\n# 새 노트\n")
    os.utime(note, (now, now))

    # 볼트 전체보다 새로운 색인. 정상이면 종료 훅이 "건너뜀" 으로 끝난다.
    # 순회 상한에 걸린 경로만 갈라 보려면 이 대조군이 있어야 한다.
    write(os.path.join(sp, "fakeidx2"), "")
    os.utime(os.path.join(sp, "fakeidx2"), (now + 600, now + 600))

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
    # 제목에 있는 말로 묻는다. 본문에도 H1 로 한 번 나오지만 그것만으로는
    # 0.15 라, 0.5 를 넘으려면 제목 가중치(0.7)가 실려야 한다.
    write(os.path.join(sp, "q3.json"),
          '{"prompt": "임시 창구가 닫혀서 답신 주소를 잃어버렸어"}\n')
    # 현황형 발화. 교훈과 안 겹쳐도 실측 의무 문구(⚑)는 붙어야 한다.
    write(os.path.join(sp, "q4.json"),
          '{"prompt": "그 프로젝트 지금 어디까지 됐는지 알려줘"}\n')
    # 12자 미만인 현황 발화. 길이 가드에 걸려도 실측 의무 문구(⚑)는 나와야
    # 한다. q4 는 21자라 이 경로를 한 번도 안 지났다 — 정작 사람이 제일 자주
    # 쓰는 말이 이쪽인데 회귀는 긴 쪽만 지키고 있었다(2026-09-14 GPT 검토).
    write(os.path.join(sp, "q5.json"),
          '{"prompt": "지금 어디까지 됐어"}\n')
    write(os.path.join(sp, "qe.json"), '{"reason": "clear"}\n')

    # 설정 파일만으로 볼트가 풀리는지 보는 자리.
    write(os.path.join(sp, "plugindata", "config.json"),
          '{"vault_dir": "%s/vault"}\n' % sp.replace("\\", "/"))

    for empty in ("nopy", "emptydata", "emptyhome", "xdg", "xdgcache"):
        os.makedirs(os.path.join(sp, empty), exist_ok=True)

    # 느린 npm. `npm root -g` 를 부르면 상한에 걸리도록 오래 끈다.
    # **판을 둘 만든다.** 훅은 파이썬 subprocess 로 npm 을 부르는데, Windows 의
    # CreateProcess 는 PATHEXT 를 보지 않으므로 확장자 없는 `#!/bin/sh` 파일을
    # 띄우지 못한다. `paths._npm_root_qmd` 가 `npm` 다음에 `npm.cmd` 를 시도하는
    # 것이 그 때문이고, 자산도 같은 두 이름을 갖춰야 양쪽에서 실제로 불린다.
    #
    # 불렸다는 증거를 파일로 남긴다. 이 자산은 "느린 npm 을 흉내 낸다"고 적혀만
    # 있고 정작 한 번도 안 불리던 기간이 있었다(2026-09-11 발견). 불렸는지를
    # 시험이 직접 센다.
    marker = os.path.join(sp, "npmcalled").replace("\\", "/")
    # 끄는 시간은 `paths.NPM_TIMEOUT`(3초)의 두 배 남짓이면 족하다. 30초를 끌던
    # 동안 시험 3회에 ping 프로세스 15개가 고아로 남았다 — subprocess 의 timeout
    # 은 부른 자식만 죽이고 그 아래 손자는 안 죽인다. 재는 동안 백그라운드가
    # 쌓이면 그 다음 측정이 그만큼 느려져, 바로 이 시험이 고치려던 문제가 된다.
    write(os.path.join(sp, "slownpm", "npm"),
          "#!/bin/sh\necho called >> '" + marker + "'\nsleep 8\n", True)

    # cmd 판. `timeout /t` 는 stdin 이 리다이렉트되면 거부하므로 ping 으로 끈다.
    # PATH 를 자산 폴더로 덮어쓴 채 불리기 때문에 ping 도 절대경로여야 한다.
    if os.name == "nt":
        ping = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                            "System32", "ping.exe")
        write(os.path.join(sp, "slownpm", "npm.cmd"),
              "@echo off\r\n"
              '>>"' + marker.replace("/", "\\") + '" echo called\r\n'
              '"' + ping + '" -n 9 127.0.0.1 >nul\r\n')

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
    """N 회 재서 최솟값. 회차마다 캐시 폴더를 새로 준다.

    캐시를 물려주면 첫 회차가 qmd 경로를 적어 두고 나머지 넷은 그것을 읽는다.
    그러면 "캐시 없음" 이라는 최악 조건이 첫 회차에만 성립한다. 실제로 그
    상태로 돌고 있었다(2026-09-11 발견).
    """
    lo = None
    for i in range(N):
        env = dict(os.environ)
        data = os.path.join(os.environ["LESSONS_TEST_DATA"], str(i))
        os.makedirs(data, exist_ok=True)
        env["CLAUDE_PLUGIN_DATA"] = data
        with open(stdin, "rb") as f:
            t = time.perf_counter()
            subprocess.run([sys.executable] + argv, stdin=f, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ms = (time.perf_counter() - t) * 1000
        lo = ms if lo is None else min(lo, ms)
    return lo


null = os.devnull
floor = best(["-c", "pass"], null)
hook = best([HOOK], STDIN)
print("%%d %%d %%d" %% (round(hook - floor), round(floor), round(hook)))
''' % HERE)

    # 검색기가 반드시 예외를 던지는 훅 트리. 실측 의무 문구는 검색과 독립이라고
    # 적혀 있지만 출력이 검색 뒤에 있어서, 예외가 나면 문구까지 같이 사라졌다.
    # builtin_search 는 OSError 를 이미 다 잡으므로 볼트를 망가뜨리는 것으로는
    # 재현되지 않는다. 그래서 훅 전체를 복사하고 search.py 만 갈아 끼운다.
    bh = os.path.join(sp, "brokenhooks")
    if os.path.isdir(bh):
        shutil.rmtree(bh)
    shutil.copytree(os.path.join(HERE, "hooks"), bh)
    write(os.path.join(bh, "search.py"),
          "# 시험용 대역. 이 모듈은 늘 실패한다.\n"
          "def search(*a, **k):\n"
          "    raise RuntimeError('시험용 강제 실패')\n")

    print("자산을 만들었다: " + sp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
