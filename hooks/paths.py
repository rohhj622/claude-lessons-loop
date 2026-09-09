"""훅이 쓰는 경로를 한 곳에서 해석한다. 절대경로를 스크립트에 직접 박지 말 것.

설정은 환경변수 셋뿐이다.

  LESSONS_VAULT   (필수) 교훈 마크다운을 둘 폴더. 이 아래에 Lessons/ 가 있어야 한다.
  QMD_BIN         (선택) qmd 진입점. 안 주면 표준 npm 전역 설치 위치를 훑는다.
  QMD_INDEX       (선택) 색인 파일. 안 주면 ~/.cache/qmd/index.sqlite

LESSONS_VAULT 가 없거나 그 폴더가 없으면 VAULT 는 빈 문자열이 되고, 훅들은
아무것도 하지 않고 조용히 통과한다. 설치만 하고 설정을 안 한 사람의 세션을
훅이 막아서는 안 된다.

같은 디스크를 Windows(Git Bash)는 `C:/...`, WSL 은 `/mnt/c/...` 로 부른다.
LESSONS_VAULT 를 한쪽 표기로만 적어 두어도 반대쪽에서 돌도록 여기서 바꿔 본다.
"""
import os


def _both_forms(p):
    """C:/x 와 /mnt/c/x 를 서로 변환해 후보 목록으로 돌려준다."""
    if not p:
        return []
    p = os.path.expanduser(p).replace("\\", "/")
    out = [p]
    if len(p) > 2 and p[1] == ":" and p[2] == "/":
        out.append("/mnt/" + p[0].lower() + p[2:])
    elif p.startswith("/mnt/") and len(p) > 6 and p[6] == "/":
        out.append(p[5].upper() + ":" + p[6:])
    return out


def _first_existing(candidates, default=""):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return default


VAULT = _first_existing(_both_forms(os.environ.get("LESSONS_VAULT", "")))

# qmd 는 `node <이 파일>` 로 부른다. 따라서 자바스크립트 진입점이어야 한다.
# shutil.which 를 쓰면 안 된다 — Windows 에서 qmd.CMD 를 돌려주고,
# `node qmd.CMD` 는 WinError 193 으로 조용히 실패한다.
#
# 플랫폼별 설치본을 먼저 본다. qmd 는 better-sqlite3(네이티브)를 쓰므로
# Windows 에 깔린 것을 WSL node 로 부르면 "invalid ELF header" 로 죽는다.
# 경로만 공유해서는 안 되고, 각 플랫폼에 설치본이 따로 있어야 한다.
_HOME = os.path.expanduser("~").replace("\\", "/")
_PKG = "/node_modules/@tobilu/qmd/bin/qmd"
_WIN_QMD = [h + "/AppData/Roaming/npm" + _PKG for h in _both_forms(_HOME)]
_NIX_QMD = [
    "/usr/local/lib" + _PKG,
    _HOME + "/.npm-global/lib" + _PKG,
    _HOME + "/.nvm/versions/node/current/lib" + _PKG,
]
_ON_WSL = os.path.isdir("/mnt/c") and os.name == "posix"

QMD = os.environ.get("QMD_BIN", "") or _first_existing(
    _NIX_QMD + _WIN_QMD if _ON_WSL else _WIN_QMD + _NIX_QMD)

# WSL 에서 Windows 설치본밖에 없으면 못 쓴다 — 빈 값으로 만들어 조용히 건너뛰게 한다.
if _ON_WSL and QMD and "/AppData/Roaming/npm/" in QMD:
    QMD = ""

INDEX = os.environ.get("QMD_INDEX", "") or _first_existing(
    [h + "/.cache/qmd/index.sqlite" for h in _both_forms(_HOME)],
    default=_HOME + "/.cache/qmd/index.sqlite")


if __name__ == "__main__":
    for k in ("VAULT", "QMD", "INDEX"):
        v = globals()[k]
        print("{0:7} {1:<70} {2}".format(
            k, v or "(없음)", "OK" if v and os.path.exists(v) else "MISSING"))
