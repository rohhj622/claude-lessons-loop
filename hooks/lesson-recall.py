#!/usr/bin/env python
"""UserPromptSubmit 훅 — 프롬프트와 의미가 가까운 교훈(LSN)을 주입한다.

어떤 경우에도 exit 0으로 끝난다. exit 2는 프롬프트를 차단하고 지워버리므로
이 스크립트에서는 절대 나오면 안 된다.
"""
import sys, json, re, os, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_md  # noqa: E402
import search  # noqa: E402
import paths  # noqa: E402
from paths import (VAULT, INDEX, NODE, option, qmd_timeout_with_source,  # noqa: E402
                   env_with_node)

# ── 조정 지점. plugin.json 의 userConfig 로 선언돼 있고, 플러그인을 켤 때 묻는다. ──
# 이 파일을 직접 고치지 말 것 — /plugin update 가 덮어쓴다.
MIN_SCORE = option("min_score", 0.35, cast=float)           # qmd 눈금
BUILTIN_MIN_SCORE = option("builtin_min_score", 0.12, cast=float)  # 겹침 눈금
MAX_HITS = int(option("max_hits", 3, cast=float))
MIN_PROMPT = 12     # 글자. 이건 굳이 설정으로 뺄 값이 아니다
QMD_TIMEOUT = qmd_timeout_with_source()[0]

# 훅 자체의 제한보다 작아야 한다. 자르는 판단은 paths.py 한 곳에서 한다 —
# doctor.py 도 같은 함수를 불러 **실제로 먹는 값**을 보여 준다.
                    # 20s 였을 때는 훅이 12s 에 먼저 죽어, 타임아웃 시 색인 신선도
                    # 경고를 내보내는 아래 폴백 경로가 실행될 기회가 없었다.
                    # 실측 왕복(2026-08-04, 서로 다른 프롬프트 5건): 웜 3.4s,
                    # 콜드 7.9~8.7s, 꼬리 1건은 12s 초과로 리콜 실패.
                    # 꼬리를 살리려고 20s 로 올리면 느린 프롬프트마다 20초를 문다.
                    # 놓친 건은 on-demand 검색으로 당겨오는 쪽이 싸다 — 상시 주입의
                    # 상한을 12s 로 못박고, 그 위는 포기한다(의도된 손실).

# 컬렉션에 따라 qmd://vault/Lessons/LSN-....md 또는 qmd://lessons/LSN-....md 로
# 나오므로 파일명만 본다. INDEX.md는 이 패턴에 걸리지 않아 자연히 배제된다.
LSN_RE = re.compile(r"(LSN-\d{4}-\d{2}-\d{2}-\d{3})\.md$")

# 현황·라이브형 질문의 표지. 넓게 잡는다 — 아래 live_gate() 주석 참조.
# 한국어 전용이다. 다른 말로 쓰는 볼트는 live_gate 옵션으로 끈다.
LIVE_RE = re.compile(
    r"어디까지|어디쯤|진행\s*상황|진척|뭐가\s*남|남은\s*(게|것|일)|"
    r"막힘|왜\s*막|블로커|지금\s*(상태|어떻|어디)|현재\s*상태|현황|"
    r"돌고\s*있|떠\s*있|살아\s*있|죽었|배포\s*(됐|되었|상태)|"
    r"얼마나\s*쌓|몇\s*건|적재\s*(량|됐)")
LIVE_GATE = str(option("live_gate", "true")).strip().lower() not in ("false", "0", "no", "off")


def live_gate(prompt):
    """현황·라이브형 질문이면 실측 의무 문구를 돌려준다. 아니면 None.

    2026-09-14: 볼트 PRJ 노트의 `막힘:` 에 적힌 11일 전 관측을 오늘의 사실로
    보고했다. 규칙이 없어서가 아니다 — 그 실수를 금지하는 에이전트가 있는데
    **안 불렸다**. 주입된 교훈은 추상 원칙이라 "막힘 칸 = 라이브 주장" 이라는
    판정을 스스로 해야 적용됐다. 그 판정을 여기서 대신 한다.

    처음엔 플러그인 밖의 옛 전역 훅에 넣었는데, settings.json 이 그 파일을
    안 부르고 있었다. 실제 호출 경로는 이 파일이다.

    과다 발화는 감수한다 — 오발 비용은 세 줄이고, 미발 비용은 저 사고다.
    """
    if not LIVE_GATE or not LIVE_RE.search(prompt):
        return None
    return ("⚑ 현황·라이브형 질문으로 보인다. 노트를 읽더라도 **라이브를 직접 재고** 답한다.\n"
            "  · 노트의 `막힘:` 은 그날의 관측이지 오늘의 사실이 아니다. 증거 명령이 인용돼 "
            "있어도 다시 친다.\n"
            "  · 빈 결과·종료코드 0 은 부재의 증거가 아니다. 양성 대조로 도구가 살아 있는지 "
            "먼저 가른다.")


def lesson_titles():
    """ID → (제목, 중요도) 맵. 표 읽기는 index_md 한 곳에서만 한다."""
    rows, _ = index_md.load(VAULT)
    return index_md.titles(rows)


def stale_index_note():
    """색인이 Lessons 실물보다 낡았으면 경고 문구를 돌려준다.

    2026-08-04: 색인이 5일 멈춰 LSN 25건(29%)이 검색에서 통째로 빠져 있었는데
    아무도 몰랐다. 무음 실패가 방치를 만든다 — 낡았다는 사실은 그 순간 보여야 한다.
    """
    # SQLite는 WAL 방식이라 쓰기가 index.sqlite-wal 로 먼저 간다. 본체 mtime은
    # 체크포인트 전까지 멈춰 있으므로, 본체만 보면 방금 갱신한 색인도 낡아 보인다.
    # 2026-08-25 실측: 본체 11:45 고정, -wal 만 12:45 로 갱신 → 경고가 상시 점등해
    # 신호 구실을 잃었다. 둘 중 더 최신 쪽을 색인 시각으로 본다.
    idx_m = 0.0
    for path in (INDEX, INDEX + "-wal"):
        try:
            idx_m = max(idx_m, os.path.getmtime(path))
        except OSError:
            pass
    if idx_m == 0.0:
        return "⚠ qmd 색인 파일이 없다 — `qmd update && qmd embed` 필요."
    newest = 0.0
    ldir = os.path.join(VAULT, "Lessons")
    try:
        for name in os.listdir(ldir):
            if name.endswith(".md"):
                newest = max(newest, os.path.getmtime(os.path.join(ldir, name)))
    except OSError:
        return None
    if newest > idx_m:
        days = max(0, int((newest - idx_m) // 86400))
        when = "{}일".format(days) if days else "오늘"
        return ("⚠ qmd 색인이 Lessons 실물보다 낡았다({} 전 기준) — "
                "최신 교훈이 검색에 안 잡힌다. `qmd update && qmd embed` 실행 필요.").format(when)
    return None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()

    # 기록 폴더가 없으면 아무것도 하지 않는다. 설치만 하고 설정을 안 한 사람의
    # 세션을 훅이 방해해서는 안 된다.
    #
    # qmd 는 여기서 보지 않는다. 없으면 기본 검색기가 받는다. 전에는 이 줄이
    # `not VAULT or not QMD` 여서, qmd 가 없으면 회수가 통째로 꺼졌다.
    if not VAULT:
        return

    # 가드: 서브에이전트 / 슬래시 명령 / 너무 짧은 프롬프트
    if data.get("agent_id") or prompt.startswith("/") or len(prompt) < MIN_PROMPT:
        return

    # 색인 신선도는 검색 성패와 무관하게 먼저 판정한다.
    # 검색이 타임아웃으로 죽어도 "색인이 낡았다"는 사실은 반드시 보여야 한다.
    stale = None
    try:
        stale = stale_index_note()
    except Exception:
        pass

    # 현황·라이브 질문이면 실측 의무를 같이 내보낸다. 검색 결과와 **독립적으로**
    # 조립한다 — qmd 가 죽거나 교훈이 하나도 안 잡히는 경로에서도 나가야 한다.
    gate = None
    try:
        gate = live_gate(prompt)
    except Exception:
        pass

    def emit(lines):
        lines = list(lines)
        if gate:
            if lines:
                lines.append("")
            lines.append(gate)
        if lines:
            sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))

    # 여기서 처음 qmd 를 찾는다. 못 찾으면 기본 검색기가 받는다.
    qmd_path, _ = paths.qmd()
    backend, raw, problem = search.search(
        VAULT, prompt, MAX_HITS, node=NODE, qmd=qmd_path, timeout=QMD_TIMEOUT,
        env=env_with_node())

    floor = MIN_SCORE if backend == "qmd" else BUILTIN_MIN_SCORE
    hits = [(s, i) for s, i in raw if s >= floor][:MAX_HITS]

    out = []
    if hits:
        titles = lesson_titles()
        # 어느 검색기로 뽑았는지를 밝힌다. qmd 와 기본 검색기는 눈금이 달라서
        # 같은 0.4 가 다른 뜻이다. 밝히지 않으면 점수를 잘못 읽는다.
        #
        # 이 이름은 층이 셋으로 나뉜다. 노트 frontmatter 의 키는 `impact`,
        # INDEX.md 표의 머리글은 `중요도`, 파서 내부 키는 다시 `impact` 다
        # (index_md.py 의 HEADERS 가 그 번역 지점이다). 전에는 이 줄이
        # "중요도=INDEX의 impact" 라고 적어 두 이름을 한 줄에 섞었고, 설치자가
        # "플러그인은 impact 를 안 쓰는 것인가" 로 실제로 혼동했다. 여기서 내보내는
        # 값은 INDEX 표의 중요도 칸에서 온 것이므로 그대로 적는다.
        out.append("이 프롬프트와 의미가 가까운 교훈 "
                   "(검색: {}, 관련도 0~1, 중요도=INDEX 표의 중요도 칸. "
                   "참고용 — 무관하면 무시할 것):".format(
                       "qmd 의미검색" if backend == "qmd" else "기본 검색기(글자 겹침)"))
        for s, lsn_id in hits:
            title, impact = titles.get(lsn_id, ("(제목 조회 실패)", ""))
            tag = "[관련도 {:.2f}".format(s)
            tag += " · 중요도 {}]".format(impact) if impact else "]"
            out.append("- {} [[{}]] {}".format(tag, lsn_id, title))
    # 왜 이렇게 됐는지를 남긴다. 전에는 유사도 미달인지 타임아웃인지 구분이
    # 안 돼서, 안 붙은 발화 204건의 원인을 끝내 못 갈랐다.
    for note in (problem, stale if backend == "qmd" else None):
        if note:
            if out:
                out.append("")
            out.append("⚠ " + note if note is problem else note)
    emit(out)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # 어떤 예외도 프롬프트를 막지 않는다
    sys.exit(0)
