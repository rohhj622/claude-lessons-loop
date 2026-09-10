"""Lessons/INDEX.md 표를 읽는 유일한 자리.

전에는 이 표를 두 벌로 파싱했다. 셸 훅이 awk 로 칸 번호를 세고, lesson-recall.py 가
정규식으로 또 셌다. 두 벌이라 한쪽만 고치면 조용히 갈라지고, 둘 다 **칸 순서에 묶여
있어** 열이 하나 밀리면 에러 없이 교훈이 제목 없이 나오거나 아예 안 붙었다.
그래서 한 벌로 합치고, 칸을 번호가 아니라 **머리글 이름**으로 찾는다.

머리글은 **넷이 다 있어야 한다.** 전에는 둘만 맞으면 표로 받았는데, 그러면 `제목` 만
바꿔 놔도 제목 없는 행을 에러 없이 돌려줬다(외부 검증에서 재현됨). 순서는 바꿔도
되지만 이름 넷은 다 있어야 하고, 없으면 어느 것이 없는지 말한다.

그리고 대상 0건을 성공으로 보고하지 않는다. 표를 못 찾았는지, 머리글이 모자라는지,
절을 못 찾았는지, 찾았는데 해당 행이 없는지를 갈라서 말한다. 깨끗해서 0인지 못
찾아서 0인지 구분이 안 되면 그 0은 근거가 아니다 — 이 볼트의 첫 번째 교훈이다.

읽기 전용이다. 예외를 밖으로 내보내지 않는다.

자가검사:  python index_md.py --selftest
"""
import os
import sys

# 머리글 이름 → 내부 키. 표의 칸 순서가 바뀌어도 이름으로 찾는다.
HEADERS = {
    "ID": "id",
    "제목": "title",
    "중요도": "impact",
    "날짜": "date",
}
KEY_NAME = {v: k for k, v in HEADERS.items()}

# 머리글 줄로 볼 최소 개수. 이 아래는 그냥 본문 표로 보고 지나간다.
_HEADER_HINT = 2


def _cells(line):
    """`| a | b |` 를 ['a', 'b'] 로. 양 끝의 빈 칸은 버린다.

    인용문(`>`) 안의 표는 표로 보지 않는다. 설명이나 경고를 인용문에 표로 적는 것은
    흔한 문서 관례인데, 그 표의 칸 이름이 넷 중 둘만 겹쳐도 교훈 표로 오인해
    problem 을 세웠다. session-start.py 는 problem 하나로 상시 교훈 주입을 통째로
    포기하므로, 행 파싱이 멀쩡한 채로 교훈이 0건이 된다(외부 검증에서 재현됨,
    2026-09-11). 교훈 표가 인용문 안에 들어갈 일은 없다.
    """
    if line.lstrip().startswith(">"):
        return None
    if "|" not in line:
        return None
    parts = [c.strip() for c in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts or None


def _is_divider(cells):
    return bool(cells) and all(set(c) <= set("-: ") and "-" in c for c in cells)


def _unlink(text):
    """`[LSN-...](LSN-....md)` 에서 이름만 꺼낸다. 링크가 아니면 그대로."""
    t = text.strip()
    if t.startswith("[") and "](" in t:
        return t[1:t.index("](")].strip()
    return t


def parse(text):
    """INDEX.md 본문 문자열에서 (rows, problem) 을 만든다.

    rows 는 dict 목록이고 키는 id·title·impact·date·group 이다.
    problem 은 도구가 제 구실을 못 했을 때의 한 줄이고, 정상이면 None 이다.
    """
    rows, group, cols, tables = [], "", None, 0
    problems = []

    for line in text.splitlines():
        if line.startswith("## "):
            group, cols = line[3:].strip(), None
            continue

        cells = _cells(line)
        if not cells:
            cols = None
            continue

        named = {HEADERS[c]: i for i, c in enumerate(cells) if c in HEADERS}
        if len(named) >= _HEADER_HINT:
            tables += 1
            missing = [KEY_NAME[k] for k in HEADERS.values() if k not in named]
            if missing:
                # 머리글이 모자라면 표로 받지 않는다. 받으면 제목 없는 행이
                # 에러 없이 나가고, 사용자는 그걸 "관련 교훈 없음"으로 읽는다.
                cols = None
                problems.append(
                    "'{}' 묶음의 표에 칸 이름이 없다: {} (필요한 넷: {})".format(
                        group or "(묶음 밖)", " · ".join(missing),
                        " · ".join(HEADERS)))
            else:
                cols = named
            continue

        if cols is None or _is_divider(cells):
            continue

        row = {"group": group}
        for key, i in cols.items():
            row[key] = _unlink(cells[i]) if i < len(cells) else ""
        if row.get("id", "").startswith("LSN-"):
            rows.append(row)

    if tables == 0:
        return [], ("Lessons/INDEX.md 에 머리글이 있는 표가 없다. "
                    "칸 이름은 {} 여야 한다.".format(" · ".join(HEADERS)))
    if problems:
        return rows, problems[0]
    return rows, None


def load(vault):
    """볼트에서 Lessons/INDEX.md 를 읽어 parse 한다."""
    path = os.path.join(vault, "Lessons", "INDEX.md") if vault else ""
    if not path or not os.path.isfile(path):
        return [], "Lessons/INDEX.md 를 찾지 못했다 ({})".format(
            path or "기록 폴더 미설정")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return [], "Lessons/INDEX.md 를 읽지 못했다 — {}".format(e)
    return parse(text)


def groups(rows):
    """등장 순서대로 절 이름 목록."""
    seen = []
    for r in rows:
        if r["group"] and r["group"] not in seen:
            seen.append(r["group"])
    return seen


def titles(rows):
    """ID → (제목, 중요도) 맵."""
    return {r["id"]: (r.get("title", ""), r.get("impact", "")) for r in rows}


def has_row(rows, lsn_id):
    """그 ID 의 행이 표에 실제로 있는가. 본문 아무 데나 있는 것과 다르다."""
    return any(r.get("id") == lsn_id for r in rows)


# ── 자가검사 ────────────────────────────────────────────────────────────
# 손으로 한 번 확인하고 넘어가면, 다음에 코드를 고치는 사람이 조용히 깨뜨린다.
# 실제로 그렇게 했다가 외부 검증에서 구멍 셋을 지적받았다. 판정마다 사례를 둔다.

_GOOD = """# 교훈 목록

## 검증·판단 방법론

| ID | 제목 | 중요도 | 날짜 |
|---|---|---|---|
| [LSN-2026-01-01-001](LSN-2026-01-01-001.md) | 양성 대조를 한다 | high | 2026-01-01 |
| [LSN-2026-01-01-002](LSN-2026-01-01-002.md) | 도구가 도는지 본다 | medium | 2026-01-01 |
"""

# 인용문 안 표. 칸 이름 넷 중 둘(제목·날짜)이 들어 있어 머리글로 오인되던 모양이다.
_QUOTED_NOTE = """# 교훈 목록

> 아래는 이 표를 읽는 곳을 적어 둔 설명이다. 교훈 표가 아니다.
>
> | 제목 | 소비자 | 날짜 |
> |---|---|---|
> | [LSN-2026-01-01-900](LSN-2026-01-01-900.md) | 세션 시작 훅 | 2026-01-01 |

"""


def selftest():
    cases = []

    def case(label, ok):
        cases.append((label, ok))

    rows, prob = parse(_GOOD)
    case("정상 표 → 문제 없음", prob is None)
    case("정상 표 → 행 2건", len(rows) == 2)
    case("정상 표 → 제목이 채워진다",
         titles(rows).get("LSN-2026-01-01-001", ("", ""))[0] == "양성 대조를 한다")
    case("정상 표 → 묶음 이름", groups(rows) == ["검증·판단 방법론"])

    shuffled = _GOOD.replace("| ID | 제목 | 중요도 | 날짜 |",
                             "| 중요도 | 날짜 | ID | 제목 |")
    shuffled = shuffled.replace(
        "| [LSN-2026-01-01-001](LSN-2026-01-01-001.md) | 양성 대조를 한다 | high | 2026-01-01 |",
        "| high | 2026-01-01 | [LSN-2026-01-01-001](LSN-2026-01-01-001.md) | 양성 대조를 한다 |")
    rows, prob = parse(shuffled)
    case("칸 순서를 바꿔도 읽힌다 → 문제 없음", prob is None)
    case("칸 순서를 바꿔도 읽힌다 → 제목이 채워진다",
         titles(rows).get("LSN-2026-01-01-001", ("", ""))[0] == "양성 대조를 한다")

    # 여기가 외부 검증에서 지적받은 자리다. 전에는 조용히 통과했다.
    renamed = _GOOD.replace("| ID | 제목 | 중요도 | 날짜 |",
                            "| ID | 이름 | 중요도 | 날짜 |")
    rows, prob = parse(renamed)
    case("칸 이름 하나를 바꾸면 → 문제로 보고한다", prob is not None)
    case("칸 이름 하나를 바꾸면 → 어느 것이 없는지 말한다",
         bool(prob) and "제목" in prob)
    case("칸 이름 하나를 바꾸면 → 제목 없는 행을 내보내지 않는다", rows == [])

    dropped = _GOOD.replace("| ID | 제목 | 중요도 | 날짜 |", "| ID | 중요도 | 날짜 |")
    rows, prob = parse(dropped)
    case("칸을 아예 빼면 → 문제로 보고한다", prob is not None)

    rows, prob = parse("# 교훈 목록\n\n표가 없다.\n")
    case("표가 없으면 → 문제로 보고한다", prob is not None)
    case("표가 없으면 → 행이 없다", rows == [])

    rows, _ = parse(_GOOD)
    case("has_row: 있는 ID", has_row(rows, "LSN-2026-01-01-001"))
    case("has_row: 없는 ID", not has_row(rows, "LSN-2026-01-01-999"))

    # 본문에 ID 만 적힌 것을 행으로 세면 안 된다. lint 가 이 함수를 믿는다.
    prose = _GOOD + "\n본문에서 LSN-2026-01-01-777 을 언급만 한다.\n"
    rows, _ = parse(prose)
    case("본문 언급은 행이 아니다", not has_row(rows, "LSN-2026-01-01-777"))

    # 인용문 안에 설명용 표를 두는 것은 흔한 문서 관례다. 그 표에 넷 중 둘 이상이
    # 들어 있으면 전에는 교훈 표로 오인해 problem 을 세웠고, session-start.py 가
    # 그 problem 하나로 상시 교훈 주입을 통째로 포기했다. 행 파싱은 정상이라
    # 조용히 망가진다(외부 검증에서 재현됨, 2026-09-11).
    quoted = _QUOTED_NOTE + _GOOD
    rows, prob = parse(quoted)
    case("인용문 안 표는 무시한다 → 문제 없음", prob is None)
    case("인용문 안 표는 무시한다 → 아래 교훈 표는 그대로 읽는다", len(rows) == 2)
    case("인용문 안 표는 무시한다 → 인용문 행은 교훈으로 안 센다",
         not has_row(rows, "LSN-2026-01-01-900"))

    bad = 0
    for label, ok in cases:
        if not ok:
            bad += 1
        print("%s  %s" % ("OK " if ok else "실패", label))
    print()
    print("%d/%d 통과" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else 0)
