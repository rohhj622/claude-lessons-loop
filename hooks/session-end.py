#!/usr/bin/env python
"""SessionEnd 훅 — qmd 색인이 Lessons 실물보다 낡았으면 갱신한다.

`/wrap` 의 색인 갱신 항목은 사람·에이전트가 챙겨야 하는 절차라 빠질 수 있다.
2026-08-04 에 5일 밀려 LSN 25건(29%)이 검색에서 통째로 빠진 전례가 있다.
컨텍스트가 필요 없는 순수 뒷정리라 SessionEnd 가 맞는 자리다.

SessionEnd 는 출력도 종료코드도 무시된다(문서 확인, 2026-09-02). 사람이 볼 수
있는 곳은 로그 파일뿐이므로 성공·실패·건너뜀을 전부 session-end.log 에 남긴다.

reason 값 5종(clear/resume/logout/prompt_input_exit/other)이 각각 어떤 동작에서
나오는지는 문서에 없다. 매처로 가리지 않고 전부 받되, 실제 값을 로그에 찍어
며칠 모은 뒤에 판단한다.
"""
import sys, json, os, subprocess, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import VAULT, QMD, INDEX  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session-end.log")
QMD_TIMEOUT = 120   # 초. update+embed 실측 20초 안팎이나 콜드 여유를 둔다.
                    # hooks.json 의 훅 timeout(150s) 보다 **작아야** 한다.


def log(msg):
    line = "{} {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def index_mtime():
    """WAL 방식이라 본체 mtime 은 체크포인트 전까지 멈춘다. -wal 과 더 최신 쪽을 본다."""
    m = 0.0
    for path in (INDEX, INDEX + "-wal"):
        try:
            m = max(m, os.path.getmtime(path))
        except OSError:
            pass
    return m


def lessons_mtime():
    newest = 0.0
    ldir = os.path.join(VAULT, "Lessons")
    for name in os.listdir(ldir):
        if name.endswith(".md"):
            newest = max(newest, os.path.getmtime(os.path.join(ldir, name)))
    return newest


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        data = {}
    reason = data.get("reason") or "(없음)"

    if not VAULT:
        return  # LESSONS_VAULT 미설정. 로그도 남기지 않는다
    if not QMD:
        log("reason={} 건너뜀 — qmd 실행 파일 없음".format(reason))
        return

    idx, lsn = index_mtime(), lessons_mtime()
    if idx and lsn <= idx:
        log("reason={} 건너뜀 — 색인이 최신".format(reason))
        return

    why = "색인 파일 없음" if not idx else "Lessons 가 색인보다 최신"
    for step in ("update", "embed"):
        try:
            r = subprocess.run(["node", QMD, step], capture_output=True,
                               timeout=QMD_TIMEOUT)
        except Exception as e:
            log("reason={} {} 실패({}) — {}".format(reason, step, why, e))
            return
        if r.returncode != 0:
            tail = r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
            log("reason={} {} 실패 rc={} {}".format(
                reason, step, r.returncode, tail[0] if tail else ""))
            return
    log("reason={} 갱신 완료 — {}".format(reason, why))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("예외 — {}".format(e))
    sys.exit(0)
