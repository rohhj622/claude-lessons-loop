#!/usr/bin/env python3
"""PRJ 노트 형식 검사 — 읽기 전용. 파일을 고치지 않는다.

`## 현재 상태`는 진행상황의 정본이라 사람이 30초 안에 읽을 수 있어야 한다.
상한을 안 두면 /wrap 이 세션마다 덮어쓰며 자란다 — 실측에서 한 노트가
60줄·볼드 46쌍·불릿 3단까지 커져 사람이 못 읽는 상태가 됐다.

임계값은 임의 수치가 아니라 **규정을 지키고 있던 노트 15건의 실측 분포 상단**이다
(8~14줄 / 깊이 1 / 볼드 0~7). 자기 기록에 맞게 고쳐도 되지만 근거를 남길 것.

`최근:` 의 [[이름]] 검사는 `team` 2명 이상인 노트에만 건다. 혼자 쓰는 동안은
잠들어 있다가 팀원이 `team` 에 추가되는 순간 저절로 깨어난다.
잠든 검사가 살아 있는지는 `python _Meta/lint.py --selftest` 로 확인한다.

호출 지점은 /wrap 이다. 훅에는 걸지 않는다 — 안 불리는 검사는 조용히 죽는다.

허용 어휘(PROGRAMS)와 필수 필드는 `_Meta/lint.config.json` 에서 읽는다.
자기 조직 어휘로 그 파일을 고친다. 파일이 없으면 아래 기본값을 쓴다.

사용법:  python _Meta/lint.py
"""
import json
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_index_md():
    """INDEX.md 파서를 찾아 온다. 못 찾으면 None.

    표를 읽는 코드는 hooks/index_md.py 한 벌뿐이다. 여기서 비슷한 것을 또 짜면
    두 벌이 되고, 한쪽만 고치는 순간 조용히 갈린다. 그래서 **찾아 쓰거나, 못
    찾으면 검사를 안 한다**. 약한 검사로 조용히 대체하지 않는다 — 그 결과는
    "통과"로 보이는데 실제로는 아무것도 확인하지 않은 상태다.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    roots = [here]
    for env in ("LESSONS_LOOP_HOOKS", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        v = os.environ.get(env, "")
        if v:
            roots.append(os.path.join(v, "hooks") if env != "LESSONS_LOOP_HOOKS" else v)
    for r in roots:
        if os.path.isfile(os.path.join(r, "index_md.py")):
            sys.path.insert(0, r)
            try:
                import index_md
                return index_md
            except Exception:
                return None
    return None


INDEX_MD = _find_index_md()

MAX_LINES = 12
MAX_DEPTH = 1
MAX_BOLD = 6
KEYS = ("요약:", "최근:", "다음:", "막힘:")

# frontmatter 필수 필드. end_date 는 뺀다 — 진행 중이면 비는 것이 정상이다.
DEFAULT_REQUIRED = ("type", "project_type", "id", "aliases", "name", "status",
                    "priority", "program", "owner", "team", "start_date",
                    "updated", "tags")

# program 의 상위 어휘. 새 갈래가 생기면 _Meta/스키마.md 와 설정 파일을 같이 고친다.
DEFAULT_PROGRAMS = ("연구", "용역", "운영", "개인연구")


def _config():
    """_Meta/lint.config.json 이 있으면 어휘를 거기서 읽는다. 없으면 기본값."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "lint.config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_CFG = _config()
REQUIRED = tuple(_CFG.get("required") or DEFAULT_REQUIRED)
PROGRAMS = tuple(_CFG.get("programs") or DEFAULT_PROGRAMS)

# 골격 절. 다수 빈도를 정본으로 삼는다. 프로젝트 고유 절은 검사 대상이 아니다.
CANON = {
    "목적": "개요",
    "이슈": "이슈 목록",
    "자료원 (Sources)": "자료원",
    "산출 대상 (Targets)": "산출물",
    "산출물 (Targets)": "산출물",
}

BULLET = re.compile(r"^(\s*)-\s")
UPDATED = re.compile(r"^updated:\s*(\S+)", re.M)
STAMP = re.compile(r"<!--\s*최종 갱신:\s*(\S+)")
TEAM = re.compile(r"^team:\s*\[(.*)\]\s*$", re.M)
WIKILINK = re.compile(r"\[\[[^\]]+\]\]")
FIELD = re.compile(r"^([a-z_]+):\s*(.*)$")


def frontmatter(text):
    """frontmatter 의 `키: 값` 을 dict 로. 빈 값도 그대로 담는다."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    body = text[3:end] if end > 0 else ""
    out = {}
    for line in body.split("\n"):
        m = FIELD.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def check_frontmatter(text):
    """필수 필드 누락과 program 어휘 위반을 돌려준다."""
    fm = frontmatter(text)
    bad = []

    # 줄이 아예 없는 것과 빈 값을 같이 잡는다.
    # `program: []` 형태가 5건 있었으므로 '줄이 있으면 통과'로는 못 잡는다.
    missing = [k for k in REQUIRED if fm.get(k, "") in ("", "[]", '""', "[ ]")]
    if missing:
        bad.append("frontmatter 누락·빈값: " + " ".join(missing))

    # program 값의 상위(`상위:하위` 면 `:` 앞)가 허용 어휘에 드는지.
    values = re.findall(r'"([^"]*)"', fm.get("program", ""))
    unknown = sorted({v.split(":")[0] for v in values} - set(PROGRAMS))
    if unknown:
        bad.append("program 어휘 밖: " + " ".join(unknown)
                   + " (허용: " + " ".join(PROGRAMS) + ")")
    return bad


def team_size(text):
    """frontmatter `team` 의 인원 수. 없거나 못 읽으면 0."""
    m = TEAM.search(text)
    if not m:
        return 0
    return len(WIKILINK.findall(m.group(1)))


def status_block(lines):
    """`## 현재 상태` 다음 줄부터 다음 `## ` 전까지."""
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "## 현재 상태")
    except StopIteration:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return lines[start + 1:end]


def check(path):
    """위반 문자열 목록을 돌려준다. 없으면 빈 리스트."""
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    bad = check_frontmatter(text)

    block = status_block(lines)
    if block is None:
        return bad + ["`## 현재 상태` 블록 없음 (CLAUDE.md 필수 항목)"]

    # 갱신일 주석은 본문이 아니므로 줄 수에서 뺀다
    body = [l for l in block if l.strip() and "최종 갱신:" not in l]

    if len(body) > MAX_LINES:
        bad.append("현재 상태 %d줄 (상한 %d)" % (len(body), MAX_LINES))

    depth = max((len(m.group(1)) // 2 + 1 for m in
                 (BULLET.match(l) for l in body) if m), default=0)
    if depth > MAX_DEPTH:
        bad.append("불릿 %d단 (상한 %d단)" % (depth, MAX_DEPTH))

    bold = sum(l.count("**") for l in body) // 2
    if bold > MAX_BOLD:
        bad.append("볼드 %d쌍 (상한 %d쌍)" % (bold, MAX_BOLD))

    missing = [k for k in KEYS if not any(k in l for l in body)]
    if missing:
        bad.append("키 누락: " + " ".join(missing))

    # 여럿이 쓰는 프로젝트에서만 `최근:` 에 [[이름]] 을 요구한다.
    # 혼자면 쓸 사람이 하나라 정보가 없고, 여럿이면 충돌 시 남길 줄을 가르는 근거가 된다.
    if team_size(text) >= 2:
        recent = [l for l in body if "최근:" in l]
        unnamed = [l for l in recent if not WIKILINK.search(l.split("최근:", 1)[1])]
        if unnamed:
            bad.append("`최근:` %d줄에 [[이름]] 없음 (team %d명)"
                       % (len(unnamed), team_size(text)))

    for l in lines:
        if l.startswith("## "):
            name = l[3:].strip()
            if name in CANON:
                bad.append("헤딩 '%s' → '%s' 로 통일" % (name, CANON[name]))

    fm = UPDATED.search(text)
    st = STAMP.search(text)
    if fm and st and fm.group(1) != st.group(1):
        bad.append("updated(%s) ≠ 최종 갱신 주석(%s)" % (fm.group(1), st.group(1)))

    return bad


def selftest():
    """잠든 검사가 실제로 도는지 확인한다.

    통과만 보고 넘기면 검사가 안 도는 것을 못 본다. 여기서 일부러 위반을
    만들어 걸리는지 본다.
    """
    import tempfile
    p0 = PROGRAMS[0]
    p1 = PROGRAMS[1 % len(PROGRAMS)]
    two = '---\nteam: ["[[A]]", "[[B]]"]\n---\n\n## 현재 상태\n'
    one = '---\nteam: ["[[A]]"]\n---\n\n## 현재 상태\n'
    keys = "- 요약: x\n- 다음: x\n- 막힘: 없음\n"
    cases = [
        ("2인·이름 없음 → 걸려야 함", two + keys + "- 최근: 뭔가 했다\n", True),
        ("2인·이름 있음 → 통과해야 함", two + keys + "- 최근: [[A]] 뭔가 했다\n", False),
        ("1인·이름 없음 → 통과해야 함", one + keys + "- 최근: 뭔가 했다\n", False),
    ]
    ok = True

    # frontmatter 검사. 필수 13개를 채운 것을 정상으로 두고 하나씩 무너뜨린다.
    full = ('---\n' + ''.join('%s: x\n' % k for k in REQUIRED
                              if k not in ("program", "team"))
            + 'program: ["%s"]\n' % p0
            + 'team: ["[[A]]"]\n---\n')
    fm_cases = [
        ("필수 다 채움 → 통과해야 함", full, "frontmatter 누락", False),
        ("program 빈 배열 → 걸려야 함",
         full.replace('program: ["%s"]' % p0, "program: []"), "frontmatter 누락", True),
        ("program 줄 없음 → 걸려야 함",
         full.replace('program: ["%s"]\n' % p0, ""), "frontmatter 누락", True),
        ("start_date 빈값 → 걸려야 함",
         full.replace("start_date: x", "start_date:"), "frontmatter 누락", True),
        ("어휘 밖 갈래명 → 걸려야 함",
         full.replace('["%s"]' % p0, '["없는갈래"]'), "program 어휘 밖", True),
        ("상위:하위 표기 → 통과해야 함",
         full.replace('["%s"]' % p0, '["%s:하위"]' % p0), "program 어휘 밖", False),
        ("복수값 → 통과해야 함",
         full.replace('["%s"]' % p0, '["%s", "%s"]' % (p0, p1)), "program 어휘 밖", False),
    ]
    for label, text, needle, should_fail in fm_cases:
        hit = any(needle in b for b in check_frontmatter(text))
        if hit != should_fail:
            ok = False
        print("%s  %s" % ("OK " if hit == should_fail else "실패", label))

    for label, text, should_fail in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as f:
            f.write(text)
            path = f.name
        hit = any("[[이름]] 없음" in b for b in check(path))
        os.unlink(path)
        if hit != should_fail:
            ok = False
        print("%s  %s" % ("OK " if hit == should_fail else "실패", label))

    # ── 교훈 검사 ──────────────────────────────────────────────────────
    # 이 플러그인은 교훈만으로도 도는데, 여기가 오래 비어 있었다. 손으로 한 번
    # 확인하고 자가검사에 안 넣었더니 외부 검증에서 구멍 셋을 지적받았다.
    if INDEX_MD is None:
        ok = False
        print("실패  교훈 검사 사례를 못 돌렸다 — index_md.py 를 못 찾는다")
        return 0 if ok else 1

    good_index = (
        "## 검증·판단 방법론\n\n"
        "| ID | 제목 | 중요도 | 날짜 |\n|---|---|---|---|\n"
        "| [LSN-2026-01-01-001](LSN-2026-01-01-001.md) | 제목 | high | 2026-01-01 |\n")
    rows, _ = INDEX_MD.parse(good_index)
    stem = "LSN-2026-01-01-001"
    full_fm = {"impact": "high", "id": stem}

    lesson_cases = [
        ("교훈 정상 → 통과해야 함", full_fm, rows, "ok", None, False),
        ("impact 없음 → 걸려야 함",
         {"id": stem}, rows, "ok", "impact 없음", True),
        ("impact 어휘 밖 → 걸려야 함",
         {"impact": "아주높음", "id": stem}, rows, "ok", "어휘 밖", True),
        ("id 가 파일명과 다름 → 걸려야 함",
         {"impact": "high", "id": "LSN-2026-01-01-999"}, rows, "ok", "파일명", True),
        ("INDEX 에 행 없음 → 걸려야 함",
         full_fm, [], "ok", "행이 없다", True),
        ("INDEX 파일 자체가 없음 → 걸려야 함",
         full_fm, [], "missing", "INDEX.md 가 없다", True),
        ("INDEX 를 못 읽음 → 걸려야 함",
         full_fm, [], "unreadable", "못 읽어", True),
    ]
    for label, fm, rws, state, needle, should_fail in lesson_cases:
        probs = lesson_problems(fm, stem, rws, state)
        hit = bool(probs) if needle is None else any(needle in b for b in probs)
        if needle is None:
            hit = bool(probs)
        if hit != should_fail:
            ok = False
        print("%s  %s" % ("OK " if hit == should_fail else "실패", label))

    # 본문 아무 데나 ID 가 적힌 것을 행으로 세면 안 된다. 전에는 부분 문자열로
    # 봐서 통과했다.
    prose_only = good_index.replace(
        "| [LSN-2026-01-01-001](LSN-2026-01-01-001.md) | 제목 | high | 2026-01-01 |",
        "") + "\n본문에서 LSN-2026-01-01-001 을 언급만 한다.\n"
    prose_rows, _ = INDEX_MD.parse(prose_only)
    hit = any("행이 없다" in b for b in lesson_problems(full_fm, stem, prose_rows, "ok"))
    if not hit:
        ok = False
    print("%s  본문에만 ID → 걸려야 함" % ("OK " if hit else "실패"))

    return 0 if ok else 1


def lesson_problems(fm, stem, rows, index_state):
    """교훈 하나의 위반 목록. 파일을 안 읽는 순수 함수라 자가검사에서 부를 수 있다.

    index_state 는 'ok' | 'missing' | 'unreadable' 중 하나다.
    rows 는 index_md.parse 가 돌려준 표의 행 목록이다.
    """
    problems = []

    imp = str(fm.get("impact", "")).strip().strip('"')
    if not imp:
        # 없으면 세션 시작 훅의 대상에서 조용히 빠진다. 조용한 탈락이라 잡는다.
        problems.append("impact 없음 — 상시 주입 대상에서 조용히 빠진다")
    elif imp not in ("high", "medium", "low"):
        problems.append("impact 어휘 밖: %s (high|medium|low)" % imp)

    if str(fm.get("id", "")).strip().strip('"') != stem:
        problems.append("id 와 파일명이 다르다: %s ≠ %s"
                        % (fm.get("id", "(없음)"), stem))

    if index_state == "missing":
        problems.append("Lessons/INDEX.md 가 없다 — 이 교훈은 제목 없이 회수된다")
    elif index_state == "unreadable":
        problems.append("Lessons/INDEX.md 를 못 읽어 행 확인을 못 했다")
    elif not INDEX_MD.has_row(rows, stem):
        # 부분 문자열이 아니라 **표의 행**에서 본다. 본문 아무 데나 ID 가 적혀
        # 있어도 통과하던 것이 외부 검증에서 지적됐다.
        problems.append("Lessons/INDEX.md 표에 행이 없다")

    return problems


def check_lessons():
    """교훈 노트 최소 검사. 이 플러그인은 교훈만으로도 돌기 때문에 여기가 본체다.

    (위반건수, 검사한건수, 도구실패사유) 를 돌려준다. Lessons/ 가 없으면 (0, 0, None).
    """
    ldir = os.path.join(VAULT, "Lessons")
    if not os.path.isdir(ldir):
        return 0, 0, None

    if INDEX_MD is None:
        return 0, 0, ("INDEX.md 파서(index_md.py)를 못 찾아 교훈 검사를 하지 "
                      "못했다. _Meta/ 에 두거나 CLAUDE_PLUGIN_ROOT 를 준다.")

    ipath = os.path.join(ldir, "INDEX.md")
    if not os.path.isfile(ipath):
        rows, index_state = [], "missing"
    else:
        rows, prob = INDEX_MD.load(VAULT)
        index_state = "unreadable" if prob else "ok"
        if prob:
            print("Lessons/INDEX.md — " + prob)

    names = sorted(n for n in os.listdir(ldir)
                   if n.startswith("LSN-") and n.endswith(".md"))
    bad = 0
    for name in names:
        stem = name[:-3]
        try:
            with open(os.path.join(ldir, name), encoding="utf-8") as f:
                fm = frontmatter(f.read())
            problems = lesson_problems(fm, stem, rows, index_state)
        except OSError as e:
            problems = ["읽기 실패: %s" % e]
        if problems:
            bad += 1
            print(stem)
            for b in problems:
                print("    " + b)
    return bad, len(names), None


def main():
    if "--selftest" in sys.argv:
        return selftest()

    lesson_bad, lesson_n, tool_fail = check_lessons()
    if tool_fail:
        # 도구가 못 돈 것을 "위반 없음"으로 보고하지 않는다.
        print("교훈 검사 실패 — " + tool_fail)
        return 1

    pdir = os.path.join(VAULT, "Projects")
    notes = []
    for root, dirs, files in os.walk(pdir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            if name.startswith("_PRJ-") and name.endswith(".md"):
                notes.append(os.path.join(root, name))
    notes.sort()

    # 양성 대조를 두 경우로 가른다. 폴더가 아예 없으면 검사 대상이 아닌 것이고
    # (이 플러그인은 교훈만으로도 돈다), 폴더는 있는데 0건이면 스캔 실패다.
    if not notes:
        if not os.path.isdir(pdir):
            if lesson_n == 0:
                print("검사할 노트를 한 건도 못 찾았다. "
                      "Lessons/ 도 Projects/ 도 없다 — 경로 설정 확인 필요.")
                return 1
            print()
            if lesson_bad:
                print("교훈 %d/%d 위반 · PRJ 노트 없음(검사 대상 아님)"
                      % (lesson_bad, lesson_n))
                return 1
            print("교훈 %d/%d OK · PRJ 노트 없음(검사 대상 아님)"
                  % (lesson_n, lesson_n))
            return 0
        print("Projects/ 는 있는데 PRJ 노트를 한 건도 못 찾았다. "
              "lint.py 의 경로 설정 확인 필요.")
        return 1

    bad_count = 0
    for p in notes:
        try:
            problems = check(p)
        except Exception as e:
            problems = ["읽기 실패: %s" % e]
        if problems:
            bad_count += 1
            print(os.path.basename(p)[:-3])
            for b in problems:
                print("    " + b)

    print()
    if bad_count or lesson_bad:
        print("PRJ %d/%d 위반 · 교훈 %d/%d 위반"
              % (bad_count, len(notes), lesson_bad, lesson_n))
        return 1
    print("PRJ %d/%d OK · 교훈 %d/%d OK"
          % (len(notes), len(notes), lesson_n, lesson_n))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
