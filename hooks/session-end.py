#!/usr/bin/env python
"""SessionEnd 훅 — qmd 색인이 Lessons 실물보다 낡았으면 갱신한다.

`/wrap` 의 색인 갱신 항목은 사람·에이전트가 챙겨야 하는 절차라 빠질 수 있다.
2026-08-04 에 5일 밀려 LSN 25건(29%)이 검색에서 통째로 빠진 전례가 있다.
컨텍스트가 필요 없는 순수 뒷정리라 SessionEnd 가 맞는 자리다.

SessionEnd 는 출력도 종료코드도 무시된다(문서 확인, 2026-09-02). 사람이 볼 수
있는 곳은 로그 파일뿐이므로 성공·실패·건너뜀을 전부 session-end.log 에 남긴다.

**재색인을 여기서 기다리지 않는다.** Codex 의 SessionEnd 는 기본 1초, 최대 3초다
(문서 확인, 2026-09-10). `qmd update && embed` 는 20초 안팎이라 맞출 방법이 없다.
그래서 훅은 갱신이 필요한지만 보고 분리된 프로세스를 띄운 뒤 바로 빠진다.

떨어뜨린 것이 있다. **훅이 재색인의 성패를 더는 못 본다.** 그래서 분리된 쪽이
자기 로그를 직접 남기고, 그 기록이 유일한 증거가 된다. 다음 세션에서 도는 색인
신선도 경고가 그대로 안전망이다 — 재색인이 조용히 실패하면 그 경고가 계속 뜬다.

reason 값 5종(clear/resume/logout/prompt_input_exit/other)이 각각 어떤 동작에서
나오는지는 문서에 없다. 매처로 가리지 않고 전부 받되, 실제 값을 로그에 찍어
며칠 모은 뒤에 판단한다.
"""
import sys, json, os, subprocess, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import VAULT, QMD, INDEX, NODE  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session-end.log")
QMD_TIMEOUT = 600   # 초. 분리된 프로세스가 쓰는 상한이다. 훅은 이걸 안 기다린다.
                    # 콜드 임베딩이 오래 걸릴 수 있어 넉넉히 둔다.


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


def reindex(why):
    """실제 재색인. 분리된 프로세스에서 돈다. 성패를 로그에만 남긴다."""
    for step in ("update", "embed"):
        try:
            r = subprocess.run([NODE, QMD, step], capture_output=True,
                               timeout=QMD_TIMEOUT)
        except Exception as e:
            log("분리 {} 실패({}) — {}".format(step, why, e))
            return
        if r.returncode != 0:
            tail = r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
            log("분리 {} 실패 rc={} {}".format(
                step, r.returncode, tail[0] if tail else ""))
            return
    log("분리 갱신 완료 — {}".format(why))


def spawn(why):
    """자기 자신을 --reindex 로 분리해 띄운다. 부모는 기다리지 않는다."""
    cmd = [sys.executable, os.path.abspath(__file__), "--reindex", why]
    kw = {"stdin": subprocess.DEVNULL,
          "stdout": subprocess.DEVNULL,
          "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        # 부모가 죽어도 살아남게 한다. 콘솔 창도 띄우지 않는다.
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                               | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200))
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)


def main():
    if "--reindex" in sys.argv:
        i = sys.argv.index("--reindex")
        reindex(sys.argv[i + 1] if len(sys.argv) > i + 1 else "(사유 없음)")
        return

    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        data = {}
    reason = data.get("reason") or "(없음)"

    if not VAULT:
        return  # 기록 폴더 미설정. 로그도 남기지 않는다
    if not QMD:
        log("reason={} 건너뜀 — qmd 실행 파일 없음".format(reason))
        return

    idx, lsn = index_mtime(), lessons_mtime()
    if idx and lsn <= idx:
        log("reason={} 건너뜀 — 색인이 최신".format(reason))
        return

    why = "색인 파일 없음" if not idx else "Lessons 가 색인보다 최신"
    try:
        spawn(why)
        log("reason={} 재색인을 분리해 띄웠다 — {}".format(reason, why))
    except Exception as e:
        log("reason={} 분리 실패 — {}".format(reason, e))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("예외 — {}".format(e))
    sys.exit(0)
