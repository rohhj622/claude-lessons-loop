"""훅이 쓰는 경로를 한 곳에서 해석한다. 절대경로를 스크립트에 직접 박지 말 것.

설정은 환경변수 셋뿐이다.

  LESSONS_VAULT   (필수) 교훈 마크다운을 둘 폴더. 이 아래에 Lessons/ 가 있어야 한다.
  QMD_BIN         (선택) qmd 진입점. 안 주면 아래 순서로 찾는다.
  QMD_INDEX       (선택) 색인 파일. 안 주면 ~/.cache/qmd/index.sqlite

LESSONS_VAULT 가 없거나 그 폴더가 없으면 VAULT 는 빈 문자열이 되고, 훅들은
아무것도 하지 않고 조용히 통과한다. 설치만 하고 설정을 안 한 사람의 세션을
훅이 막아서는 안 된다.

같은 디스크를 Windows(Git Bash)는 `C:/...`, WSL 은 `/mnt/c/...` 로 부른다.
LESSONS_VAULT 를 한쪽 표기로만 적어 두어도 반대쪽에서 돌도록 여기서 바꿔 본다.

qmd 탐색은 경로를 나열하지 않고 물어보는 쪽을 정본으로 삼는다. 나열식은
Homebrew·nvm·fnm·volta·asdf·mise 가 각자 다른 곳에 깔아서 반드시 새는데,
`npm root -g` 는 어느 방식이든 자기가 쓰는 자리를 답한다. 다만 subprocess 라
발화마다 도는 훅에서 매번 돌리기는 아까우므로 순서를 이렇게 둔다.

  1. QMD_BIN            사람이 직접 준 것이 언제나 이긴다
  2. 캐시               이전에 찾아 둔 경로가 아직 살아 있으면 그대로
  3. 나열식 후보        subprocess 없이 끝나는 흔한 경우
  4. `npm root -g`      위가 다 새면 그때 물어본다. 찾으면 캐시에 남긴다
"""
import os
import subprocess

_PKG = "/node_modules/@tobilu/qmd/bin/qmd"


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


_HOME = os.path.expanduser("~").replace("\\", "/")
_ON_WSL = os.path.isdir("/mnt/c") and os.name == "posix"


# ── 설정값 ──────────────────────────────────────────────────────────────
# 조정값을 훅 파일 안에 두면 안 된다. ${CLAUDE_PLUGIN_ROOT} 아래는 플러그인이
# 소유하는 자리라 `/plugin update` 가 덮어쓴다. 사용자가 맞춰 놓은 값이 갱신
# 한 번에 조용히 원래대로 돌아가고, 훅은 계속 exit 0 으로 끝나니 아무도 못 본다.
#
# 그래서 plugin.json 의 userConfig 로 선언한다. Claude Code 가 플러그인을 켤 때
# 묻고, 값을 CLAUDE_PLUGIN_OPTION_<키를 대문자로> 로 훅 프로세스에 넣어 준다.
# 환경변수를 직접 준 사람이 언제나 이긴다 — CI 와 임시 실행에서 쓸모가 있다.

def option(key, default=None, env=None, cast=None):
    """설정값 하나. (값, 어디서 왔는지) 가 아니라 값만 돌려준다.

    출처까지 알고 싶으면 option_with_source 를 쓴다. doctor.py 가 그쪽을 쓴다.
    """
    return option_with_source(key, default, env, cast)[0]


def option_with_source(key, default=None, env=None, cast=None):
    for name, where in ((env, "환경변수 " + str(env)),
                        ("CLAUDE_PLUGIN_OPTION_" + key.upper(), "플러그인 설정")):
        if not name:
            continue
        raw = os.environ.get(name, "").strip()
        if not raw:
            continue
        if cast is None:
            return raw, where
        try:
            return cast(raw), where
        except (TypeError, ValueError):
            # 값이 망가졌다고 훅이 죽으면 안 된다. 기본값으로 간다.
            return default, "{}의 값이 잘못돼 기본값을 쓴다".format(where)
    return default, "기본값"


# 훅 자체의 제한(hooks.json 의 timeout). 검색은 이보다 먼저 끝나야 한다 —
# 훅이 먼저 죽으면 "색인이 낡았다"는 경고까지 같이 사라진다. 20초로 잡았다가
# 실제로 그렇게 만든 적이 있다. 사용자가 크게 잡아도 여기서 자른다.
RECALL_HOOK_TIMEOUT = 15
_TIMEOUT_CAP = RECALL_HOOK_TIMEOUT - 3


def qmd_timeout_with_source():
    raw, src = option_with_source("qmd_timeout", 12.0, cast=float)
    val = float(raw)
    if val > _TIMEOUT_CAP:
        return float(_TIMEOUT_CAP), "{}에 적힌 {:g}초가 상한을 넘어 잘랐다".format(
            src, val)
    return val, src


VAULT = _first_existing(_both_forms(option("vault_dir", "", env="LESSONS_VAULT")))


# ── 캐시 ────────────────────────────────────────────────────────────────
# CLAUDE_PLUGIN_DATA 는 플러그인 갱신을 견디고 제거할 때 같이 지워지는 자리다.
# 훅이 아닌 곳에서 부르면 없을 수 있고, 그때는 그냥 캐시 없이 간다.

def _cache_path(name):
    d = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return os.path.join(d, name) if d else ""


def _cache_read(name):
    p = _cache_path(name)
    if not p:
        return ""
    try:
        with open(p, encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        return ""
    return v if v and os.path.exists(v) else ""


def _cache_write(name, value):
    p = _cache_path(name)
    if not p or not value:
        return
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(value)
    except OSError:
        pass  # 캐시는 있으면 좋은 것이지 없으면 안 되는 것이 아니다


# ── qmd ─────────────────────────────────────────────────────────────────
# qmd 는 `node <이 파일>` 로 부른다. 따라서 자바스크립트 진입점이어야 한다.
# shutil.which 를 쓰면 안 된다 — Windows 에서 qmd.CMD 를 돌려주고,
# `node qmd.CMD` 는 WinError 193 으로 조용히 실패한다.
#
# 플랫폼별 설치본을 먼저 본다. qmd 는 better-sqlite3(네이티브)를 쓰므로
# Windows 에 깔린 것을 WSL node 로 부르면 "invalid ELF header" 로 죽는다.
# 경로만 공유해서는 안 되고, 각 플랫폼에 설치본이 따로 있어야 한다.

_WIN_QMD = [h + "/AppData/Roaming/npm" + _PKG for h in _both_forms(_HOME)]
_NIX_QMD = [
    "/opt/homebrew/lib" + _PKG,      # macOS Apple Silicon, Homebrew
    "/usr/local/lib" + _PKG,         # macOS Intel, Homebrew · 리눅스 기본
    "/usr/lib" + _PKG,               # 배포판 패키지
    _HOME + "/.npm-global/lib" + _PKG,
    _HOME + "/.local/share/fnm" + _PKG,
    _HOME + "/.volta/tools/image/node" + _PKG,
]


def _nvm_candidates():
    """nvm 은 `current` 심볼릭 링크를 기본으로 만들지 않는다. 실제 버전 폴더를 훑는다."""
    base = _HOME + "/.nvm/versions/node"
    try:
        vers = sorted(os.listdir(base), reverse=True)
    except OSError:
        return []
    return [base + "/" + v + "/lib" + _PKG for v in vers]


def _npm_root_qmd():
    """`npm root -g` 에게 전역 모듈 루트를 물어본다. 마지막 수단."""
    for npm in ("npm", "npm.cmd"):
        try:
            r = subprocess.run([npm, "root", "-g"], capture_output=True, timeout=10)
        except Exception:
            continue
        if r.returncode != 0:
            continue
        root = r.stdout.decode("utf-8", "replace").strip().replace("\\", "/")
        if not root:
            continue
        cand = root + "/@tobilu/qmd/bin/qmd"
        if os.path.exists(cand):
            return cand
    return ""


def _find_qmd():
    """돌려주는 값은 (경로, 어떻게 찾았는지). 못 찾으면 ("", 이유)."""
    env = os.environ.get("QMD_BIN", "")
    if env:
        return (env, "QMD_BIN 환경변수")

    cached = _cache_read("qmd-path")
    if cached:
        return (cached, "캐시")

    listed = _NIX_QMD + _nvm_candidates() + _WIN_QMD if _ON_WSL \
        else _WIN_QMD + _NIX_QMD + _nvm_candidates()
    hit = _first_existing(listed)
    if hit:
        _cache_write("qmd-path", hit)
        return (hit, "표준 설치 위치")

    hit = _npm_root_qmd()
    if hit:
        _cache_write("qmd-path", hit)
        return (hit, "npm root -g 조회")

    return ("", "찾지 못함 — qmd 가 설치되지 않았거나 다른 노드 환경에 있다")


QMD, QMD_HOW = _find_qmd()

# WSL 에서 Windows 설치본밖에 없으면 못 쓴다 — 네이티브 모듈이 안 맞는다.
# 빈 값으로 만들어 조용히 건너뛰게 한다.
if _ON_WSL and QMD and "/AppData/Roaming/npm/" in QMD:
    QMD, QMD_HOW = "", "WSL 인데 Windows 설치본만 있다 — WSL 쪽에 따로 설치해야 한다"


# ── node ────────────────────────────────────────────────────────────────
# GUI 로 뜬 Claude Code 는 로그인 셸 PATH 를 못 물려받을 수 있다.
# node 는 which 를 써도 된다 — Windows 에서도 node.exe 가 그대로 실행 가능하다.

def _find_node():
    cached = _cache_read("node-path")
    if cached:
        return cached
    import shutil
    hit = shutil.which("node") or ""
    if not hit:
        hit = _first_existing([
            "/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node",
        ])
    if hit:
        hit = hit.replace("\\", "/")
        _cache_write("node-path", hit)
    return hit or "node"   # 마지막에는 PATH 에 걸기를 기대한다


NODE = _find_node()


# ── 색인 ────────────────────────────────────────────────────────────────

INDEX = os.environ.get("QMD_INDEX", "") or _first_existing(
    [h + "/.cache/qmd/index.sqlite" for h in _both_forms(_HOME)],
    default=_HOME + "/.cache/qmd/index.sqlite")


if __name__ == "__main__":
    import doctor
    raise SystemExit(doctor.main())
