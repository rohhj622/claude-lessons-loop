#!/usr/bin/env python3
"""SessionStart 훅 — 노트 꼬리 닫는태그 오염을 훑는다 (탐지 전용, 수정 안 함).

서브에이전트가 노트를 쓸 때 자기 출력 래퍼의 닫는 태그를 파일 끝에 흘리는 일이
있었다. 판정 조건: 마지막 줄이 TAGS 중 하나와 정확히 일치 + 본문에 대응하는
여는 태그 없음 + 코드블록 밖(본문의 ``` 개수가 짝수).

깨끗하면 침묵한다. 항상 exit 0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import VAULT  # noqa: E402  Windows·WSL 양쪽에서 해석된다
TAGS = ("</content>", "</output>", "</result>")


def is_polluted(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    stripped = text[:-1] if text.endswith("\n") else text
    idx = stripped.rfind("\n")
    last = stripped[idx + 1:]
    if last not in TAGS:
        return False
    body = stripped[:idx + 1] if idx >= 0 else ""
    if ("<" + last[2:]) in body:
        return False
    return body.count("```") % 2 == 0


def main():
    if not VAULT:
        return  # LESSONS_VAULT 미설정
    hits, scanned = [], 0
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in (".git", "worktrees")]
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            p = os.path.join(root, name)
            scanned += 1
            try:
                if is_polluted(p):
                    hits.append(p.replace("\\", "/"))
            except Exception:
                pass
    if scanned == 0:  # 양성 대조: 스캔 0건은 '깨끗함'이 아니라 도구 실패다
        print("오염 점검 실패 — .md 를 한 건도 못 읽었다. tagscan.py 와 LESSONS_VAULT 확인 필요.")
        return
    if hits:
        print("노트 꼬리 오염(서브에이전트 Write 태그 유출) 발견. "
              "각 파일 마지막 줄을 제거할 것:")
        for h in hits:
            print(h)


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    main()
except Exception:
    pass
sys.exit(0)
