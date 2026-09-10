"""Lessons/INDEX.md 표를 읽는 유일한 자리.

전에는 이 표를 두 벌로 파싱했다. session-start.sh 가 awk 로 칸 번호를 세고,
lesson-recall.py 가 정규식으로 또 셌다. 두 벌이라 한쪽만 고치면 조용히 갈라지고,
둘 다 **칸 순서에 묶여 있어** 열이 하나 밀리면 에러 없이 교훈이 제목 없이 나오거나
아예 안 붙었다. 그래서 한 벌로 합치고, 칸을 번호가 아니라 **머리글 이름**으로 찾는다.

그리고 대상 0건을 성공으로 보고하지 않는다. 표를 못 찾았는지, 절을 못 찾았는지,
찾았는데 해당 행이 없는지를 갈라서 말한다. 깨끗해서 0인지 못 찾아서 0인지 구분이
안 되면 그 0은 근거가 아니다 — 이 볼트의 첫 번째 교훈이 그것이다.

읽기 전용이다. 예외를 밖으로 내보내지 않는다.
"""
import os

# 머리글 이름 → 내부 키. 표의 칸 순서가 바뀌어도 이름으로 찾는다.
HEADERS = {
    "ID": "id",
    "제목": "title",
    "중요도": "impact",
    "날짜": "date",
}


def _cells(line):
    """`| a | b |` 를 ['a', 'b'] 로. 양 끝의 빈 칸은 버린다."""
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


def load(vault):
    """(rows, problem) 을 돌려준다.

    rows 는 dict 목록이고 키는 id·title·impact·date·group 이다.
    problem 은 도구가 제 구실을 못 했을 때의 한 줄이고, 정상이면 None 이다.
    """
    path = os.path.join(vault, "Lessons", "INDEX.md") if vault else ""
    if not path or not os.path.isfile(path):
        return [], "Lessons/INDEX.md 를 찾지 못했다 ({})".format(path or "기록 폴더 미설정")

    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError as e:
        return [], "Lessons/INDEX.md 를 읽지 못했다 — {}".format(e)

    rows, group, cols, tables = [], "", None, 0
    for line in lines:
        if line.startswith("## "):
            group, cols = line[3:].strip(), None
            continue

        cells = _cells(line)
        if not cells:
            cols = None
            continue

        # 머리글 줄인가. 아는 이름이 둘 이상 있으면 머리글로 본다.
        named = {HEADERS[c]: i for i, c in enumerate(cells) if c in HEADERS}
        if len(named) >= 2:
            cols, tables = named, tables + 1
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
    return rows, None


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
