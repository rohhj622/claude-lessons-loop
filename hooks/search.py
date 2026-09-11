"""교훈 검색기. 백엔드 둘을 같은 모양으로 감싼다.

  qmd      의미검색. 정확하지만 전역 npm 설치와 모델 2 GB 를 요구한다.
  builtin  표준 라이브러리만 쓴다. 설치 직후 첫날부터 돈다.

qmd 를 대체하려는 것이 아니다. **없어도 도는 상태**를 만드는 것이 목적이다.
전에는 qmd 가 없으면 회수가 통째로 꺼졌고, 꺼진 줄도 모르는 것이 기본값이었다.

두 백엔드는 (점수, 교훈ID) 목록을 돌려준다. 점수는 둘 다 0~1 이라 min_score 가
같은 뜻으로 통한다. 다만 **눈금이 같지는 않다** — qmd 는 재순위까지 거친 값이고
builtin 은 토큰 겹침이다. 그래서 어느 쪽으로 뽑았는지를 호출부가 알 수 있게
백엔드 이름을 같이 돌려준다.

읽기 전용이다. 예외를 밖으로 내보내지 않는다.
"""
import os
import re
import subprocess

# Windows 에서 콘솔이 없는 부모(데스크톱 앱)가 콘솔 프로그램을 부르면 새 창이
# 뜬다. 발화마다 도는 훅이라 사람 눈에는 검은 창이 깜빡였다 사라진다.
# 실측(2026-09-11): 발화 시점에 python.exe·node.exe 와 함께 conhost.exe 둘이
# 같이 떴다. 기능은 멀쩡해서 로그로는 절대 안 잡히는 종류의 결함이다.
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW

LSN_RE = re.compile(r"(LSN-\d{4}-\d{2}-\d{2}-\d{3})\.md$")

# 한국어는 조사가 붙어 단어 단위 겹침이 안 먹는다. "타임아웃을" 과 "타임아웃" 은
# 다른 토큰이 된다. 형태소 분석기를 끌어오면 의존이 늘고 언어마다 따로 필요하다.
# 그래서 한글 구간은 **글자 2-그램**으로 자른다 — 조사가 붙어도 앞쪽 그램이 겹친다.
# 라틴 문자와 숫자는 원래 공백으로 갈리므로 단어 그대로 쓴다.
_WORD_RE = re.compile(r"[0-9A-Za-z_]{2,}")
_HANGUL_RE = re.compile(r"[가-힣]{2,}")
_NGRAM = 2


def _features(text):
    """비교 단위 집합. 라틴 단어 + 한글 2-그램."""
    low = text.lower()
    feats = set(_WORD_RE.findall(low))
    for run in _HANGUL_RE.findall(low):
        for i in range(len(run) - _NGRAM + 1):
            feats.add(run[i:i + _NGRAM])
    return feats


def _overlap(q, d):
    """질의 단위 중 문서에 나타난 비율. 0~1."""
    return (len(q & d) / len(q)) if q else 0.0


# 제목·별칭·태그는 사람이 그 교훈을 한 줄로 요약한 것이라 본문보다 신호가 세다.
_HEAD_WEIGHT = 0.7
_BODY_WEIGHT = 0.3


def _split_note(text):
    """(머리 = 프론트매터의 name·aliases·tags, 몸통 = 나머지)."""
    head, body = [], text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            fm, body = text[3:end], text[end + 4:]
            for line in fm.splitlines():
                if line.split(":", 1)[0].strip() in ("name", "aliases", "tags", "id"):
                    head.append(line.split(":", 1)[-1])
    return " ".join(head), body


def builtin_search(vault, query, limit):
    """의존 없는 검색. (점수, 교훈ID) 목록을 점수 내림차순으로."""
    ldir = os.path.join(vault, "Lessons")
    q = _features(query)
    if not q:
        return []
    out = []
    try:
        names = os.listdir(ldir)
    except OSError:
        return []
    for name in names:
        m = LSN_RE.search(name)
        if not m:
            continue          # INDEX.md 는 여기서 자연히 빠진다
        try:
            with open(os.path.join(ldir, name), encoding="utf-8",
                      errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        head, body = _split_note(text)
        score = (_HEAD_WEIGHT * _overlap(q, _features(head))
                 + _BODY_WEIGHT * _overlap(q, _features(body)))
        if score > 0:
            out.append((round(score, 2), m.group(1)))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out[:limit]


class QmdFailed(Exception):
    pass


# qmd 는 맨 질의를 받으면 **생성 모델로 질의를 19~20개로 불린다**(확장).
# 그 단계가 비용의 대부분이다 — 새 질의 10~11초, 확장을 건너뛰면 3.5초(실측
# 2026-09-11, RTX 5070). 훅은 발화마다 새 질의를 보내므로 캐시가 맞는 일이
# 없어 늘 10초대였고, 12초 상한 바로 아래에 붙어 있었다.
#
# 더 나쁜 것은 GPU 경합이다. 확장 경로는 모델 셋(생성·임베딩·재순위)을 띄워
# VRAM 을 물고, 여럿이 겹치면 재순위 컨텍스트 생성에서 깨진다. 같은 날 동시
# 실행으로 재현한 것 — 4개에서 rc=1, 8개에서 ggml 이 CUDA 오류로 abort 했다
# (rc=3221226505). `vec:` 로 부르면 같은 부하에서 4개까지 전원 성공했다.
#
# 대가는 재현율이다. 확장이 9건 찾을 때 `vec:` 는 6건을 찾았다. 훅은 상위
# 3건만 쓰므로, 12초를 넘겨 글자 겹침으로 떨어지는 것보다 낫다고 봤다.
_TYPED_PREFIX = "vec: "


def _as_typed_query(query):
    """질의를 qmd 의 타입 지정 질의서 한 줄로 만든다.

    문법이 **한 줄에 따옴표가 짝을 이룰 것**을 요구한다. 발화는 여러 줄이고
    따옴표가 홀수로 남기도 해서, 개행은 공백으로 접고 큰따옴표는 뺀다.
    """
    one_line = " ".join(query.split())
    return _TYPED_PREFIX + one_line.replace('"', " ")


def qmd_search(node, qmd, query, limit, timeout, env=None):
    """qmd 의미검색. 실패하면 예외를 올린다 — 호출부가 폴백을 정한다.

    env 는 node 디렉터리를 PATH 에 얹은 환경이다(paths.env_with_node). qmd 가
    자식 node 를 PATH 로 찾기 때문에 필요하다. 이 모듈은 paths 를 import 하지
    않으므로 호출부가 넘긴다.
    """
    r = subprocess.run(
        [node, qmd, "query", "-n", str(limit * 7), "-c", "lessons",
         "--format", "files", _as_typed_query(query)],
        capture_output=True, timeout=timeout, env=env,
        creationflags=NO_WINDOW)
    # 종료코드를 안 보면 실패가 "결과 없음"과 똑같이 생긴다. 컬렉션 이름이
    # 틀렸거나 색인이 깨졌을 때가 정확히 그 모양이다.
    if r.returncode != 0:
        tail = r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
        raise QmdFailed("종료코드 {}{}".format(
            r.returncode, " — " + tail[0] if tail else ""))
    out = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        _, score, path = parts
        m = LSN_RE.search(path.strip())
        if not m:
            continue
        try:
            out.append((float(score), m.group(1)))
        except ValueError:
            continue
    return out


def search(vault, query, limit, node="", qmd="", timeout=12, env=None):
    """(백엔드이름, 결과, 문제) 를 돌려준다.

    qmd 가 있으면 qmd 를 쓰고, 없거나 실패하면 builtin 으로 떨어진다.
    **왜 그렇게 됐는지를 problem 에 남긴다** — 전에는 유사도 미달인지
    타임아웃인지 구분이 안 돼서, 안 붙은 발화 204건의 원인을 못 갈랐다.
    """
    if qmd and node:
        try:
            return "qmd", qmd_search(node, qmd, query, limit, timeout, env), None
        except subprocess.TimeoutExpired:
            return ("builtin", builtin_search(vault, query, limit),
                    "qmd 가 {:g}초 안에 안 끝나 기본 검색기로 대신했다".format(timeout))
        except Exception as e:
            return ("builtin", builtin_search(vault, query, limit),
                    "qmd 실행이 실패해 기본 검색기로 대신했다 — {}".format(e))
    return "builtin", builtin_search(vault, query, limit), None
