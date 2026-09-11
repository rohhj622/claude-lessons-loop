#!/usr/bin/env python
"""매니페스트 둘이 갈리지 않았는지 본다.

Claude Code 는 `.claude-plugin/plugin.json` 을, Codex 는 루트 `plugin.json` 을
읽는다. 형식이 달라 한 파일로 못 쓰는데, 같은 내용을 두 곳에 두면 **한쪽만
고치는 사고가 반드시 난다.** 그리고 그 사고는 조용하다 — 한쪽 제품에서만
버전이 낡거나 이름이 어긋난 채로 계속 돈다.

사용:  python hooks/manifests.py [--selftest]

읽기 전용이다. 어긋나면 종료코드 1.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE = os.path.join(ROOT, ".claude-plugin", "plugin.json")
CODEX = os.path.join(ROOT, "plugin.json")

# 두 매니페스트가 반드시 같아야 하는 것. 표시용 문구는 갈려도 되지만
# 이름과 버전이 갈리면 설치·갱신이 서로 다른 것을 가리키게 된다.
SHARED = ("name", "version", "description", "license")


STD_HOOKS = "./hooks/hooks.json"


def compare(a, b):
    """(어긋난 항목 목록). 둘 다 dict 여야 한다."""
    bad = []
    for k in SHARED:
        av, bv = a.get(k), b.get(k)
        if av != bv:
            bad.append("{}: Claude={!r} · Codex={!r}".format(k, av, bv))

    # 훅 파일이 서로 다른 것을 가리키면 한쪽 제품만 다른 훅으로 돈다.
    #
    # Claude Code 는 hooks/hooks.json 을 **자동으로** 읽는다. 매니페스트가 그것을
    # 다시 가리키면 "이미 읽은 파일"이라며 훅 로딩 전체가 에러로 끝난다(실측
    # 2026-09-11, /plugin 화면에 Duplicate hooks file detected). 그래서 Claude
    # 쪽은 비워 두는 것이 정상이고, 표준 경로 밖의 파일을 더 얹을 때만 적는다.
    # Codex 는 자동으로 읽지 않으므로 표준 경로를 명시해야 한다.
    ah = a.get("hooks")
    bh = (b.get("extensions", {}).get("com.openai", {}) or {}).get("hooks")
    if ah is None:
        if bh != STD_HOOKS:
            bad.append("Claude 는 훅 경로를 비워 자동 로드를 쓰는데 "
                       "Codex={!r} 라 표준 경로가 아니다".format(bh))
    elif ah == STD_HOOKS:
        bad.append("Claude 매니페스트가 표준 훅 경로를 다시 가리킨다 — "
                   "자동 로드와 겹쳐 훅이 통째로 안 실린다")
    elif bh != ah:
        bad.append("hooks 경로: Claude={!r} · Codex={!r}".format(ah, bh))
    return bad


def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    missing = [p for p in (CLAUDE, CODEX) if not os.path.isfile(p)]
    if missing:
        # 하나만 있는 것을 "문제 없음"으로 보고하지 않는다. 그 상태면 한쪽
        # 제품에서 플러그인이 통째로 안 잡힌다.
        for p in missing:
            print("매니페스트 없음: " + os.path.relpath(p, ROOT))
        return 1

    bad = compare(_read(CLAUDE), _read(CODEX))
    if bad:
        print("매니페스트 둘이 어긋났다:")
        for b in bad:
            print("    " + b)
        return 1
    print("매니페스트 둘이 일치한다 (%s)" % " · ".join(SHARED))
    return 0


def selftest():
    """검사기가 어긋난 것을 정말 잡는지 본다."""
    base = {"name": "x", "version": "1.0.0", "description": "d", "license": "MIT"}
    codex = {"name": "x", "version": "1.0.0", "description": "d", "license": "MIT",
             "extensions": {"com.openai": {"hooks": "./hooks/hooks.json"}}}
    cases = [
        ("같으면 → 통과해야 함", base, codex, False),
        ("버전이 다르면 → 걸려야 함",
         base, dict(codex, version="2.0.0"), True),
        ("이름이 다르면 → 걸려야 함",
         base, dict(codex, name="y"), True),
        ("설명이 다르면 → 걸려야 함",
         base, dict(codex, description="다름"), True),
        ("Codex 훅 경로가 표준이 아니면 → 걸려야 함", base,
         {"name": "x", "version": "1.0.0", "description": "d", "license": "MIT",
          "extensions": {"com.openai": {"hooks": "./other.json"}}}, True),
        ("Claude 가 표준 경로를 다시 가리키면 → 걸려야 함",
         dict(base, hooks="./hooks/hooks.json"), codex, True),
    ]
    ok = True
    for label, a, b, should_fail in cases:
        hit = bool(compare(a, b))
        if hit != should_fail:
            ok = False
        print("%s  %s" % ("OK " if hit == should_fail else "실패", label))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
