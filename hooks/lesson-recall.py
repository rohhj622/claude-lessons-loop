#!/usr/bin/env python
"""UserPromptSubmit 훅 — 프롬프트와 의미가 가까운 교훈(LSN)을 주입한다.

어떤 경우에도 exit 0으로 끝난다. exit 2는 프롬프트를 차단하고 지워버리므로
이 스크립트에서는 절대 나오면 안 된다.
"""
import sys, json, re, os, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_md  # noqa: E402
from paths import VAULT, QMD, INDEX, NODE  # noqa: E402  Windows·WSL 양쪽에서 해석된다

# ── 여기 셋이 조정 지점이다. 각자 자기 기록에 맞춰 고친다. ──
MIN_SCORE = 0.35    # 노이즈 절단선. 실사용 뒤 조정
MAX_HITS = 3
MIN_PROMPT = 12     # 글자
QMD_TIMEOUT = 12    # 초. hooks.json 의 훅 timeout(15s)보다 **작아야** 한다.
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

    # 설정이 없으면 아무것도 하지 않는다. 설치만 하고 LESSONS_VAULT 를 안 정한
    # 사람의 세션을 훅이 방해해서는 안 된다.
    if not VAULT or not QMD:
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

    def emit(lines):
        if lines:
            sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))

    try:
        result = subprocess.run(
            [NODE, QMD, "query", "-n", "20", "-c", "lessons",
             "--format", "files", prompt],
            capture_output=True, timeout=QMD_TIMEOUT,
        )
    except Exception:
        # 타임아웃·실행 실패. 프롬프트는 막지 않되, 낡은 색인은 알린다.
        emit([stale] if stale else [])
        return

    hits = []
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(",", 2)
        if len(parts) != 3:
            continue
        _, score, path = parts
        m = LSN_RE.search(path.strip())
        if not m:
            continue
        try:
            s = float(score)
        except ValueError:
            continue
        if s < MIN_SCORE:
            continue
        hits.append((s, m.group(1)))
        if len(hits) >= MAX_HITS:
            break
    out = []
    if hits:
        titles = lesson_titles()
        out.append("이 프롬프트와 의미가 가까운 교훈 "
                   "(관련도=검색 매칭 점수 0~1, 중요도=INDEX의 impact. "
                   "참고용 — 무관하면 무시할 것):")
        for s, lsn_id in hits:
            title, impact = titles.get(lsn_id, ("(제목 조회 실패)", ""))
            tag = "[관련도 {:.2f}".format(s)
            tag += " · 중요도 {}]".format(impact) if impact else "]"
            out.append("- {} [[{}]] {}".format(tag, lsn_id, title))
    if stale:
        if out:
            out.append("")
        out.append(stale)
    emit(out)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # 어떤 예외도 프롬프트를 막지 않는다
    sys.exit(0)
