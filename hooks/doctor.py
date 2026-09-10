#!/usr/bin/env python
"""설정 점검기 — 어느 기계에서든 같은 명령으로 상태를 찍는다.

  sh hooks/py.sh doctor.py

이 플러그인은 Windows 에서 만들어졌고 맥·리눅스에서도 돌아야 한다. "내 기계에서는
된다"로는 그걸 확인할 수 없다. 그래서 판정을 사람 눈이 아니라 이 파일 하나에 모은다.
configure 스킬도 자기 판정을 따로 짜지 않고 이것을 부른다.

읽기 전용이다. 어떤 것도 고치지 않는다. 항상 exit 0 으로 끝난다 — 훅에서 불릴 수
있고, 훅은 작업을 막아서는 안 된다.
"""
import os
import platform
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


def _row(label, value, ok, hint=""):
    return (label, value, ok, hint)


def _width(s):
    """한글·한자는 터미널에서 두 칸을 먹는다. 글자 수로 세면 표가 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
               for c in s)


def _pad(s, w):
    return s + " " * max(0, w - _width(s))


def collect():
    """(이름, 값, 정상인가, 고칠 방법) 목록을 만든다."""
    rows = []

    rows.append(_row(
        "플랫폼", "{} {} · Python {}".format(
            platform.system(), platform.machine(),
            platform.python_version()), True))

    # 설정이 진짜로 없는 것과, 훅 밖에서 돌려 설정을 **볼 수 없는** 것은 다르다.
    # 둘을 같은 문구로 안내하면 이미 설정을 마친 사람이 멀쩡한 설정을 다시 만진다.
    blind = not paths.VAULT and not paths.inside_plugin_runtime()
    if paths.VAULT:
        rows.append(_row("기록 폴더", paths.VAULT, True))
    else:
        raw = os.environ.get("LESSONS_VAULT", "")
        if raw:
            hint = "폴더가 없다. 경로를 확인한다."
        elif blind:
            hint = ("훅 밖에서 돌려 플러그인 설정을 볼 수 없다. 이미 설정했다면 "
                    "정상이다 — 새 세션의 훅 출력으로 확인하거나, "
                    "LESSONS_VAULT=<경로> 를 주고 다시 돌린다.")
        else:
            hint = "/claude-lessons-loop:configure 로 설정한다."
        rows.append(_row("기록 폴더", raw or "(설정 없음)", False, hint))

    idx_md = os.path.join(paths.VAULT, "Lessons", "INDEX.md") if paths.VAULT else ""
    if idx_md and os.path.isfile(idx_md):
        n = 0
        try:
            for name in os.listdir(os.path.join(paths.VAULT, "Lessons")):
                if name.startswith("LSN-") and name.endswith(".md"):
                    n += 1
        except OSError:
            pass
        rows.append(_row("교훈 목록", "{} (교훈 {}건)".format(idx_md, n), True))
    else:
        rows.append(_row(
            "교훈 목록", idx_md or "(기록 폴더 없음)", False,
            "기록 폴더를 못 봐서 확인하지 못했다. 위 줄을 먼저 푼다." if blind else
            "Lessons/INDEX.md 가 없다. configure 로 템플릿을 복사한다."))

    # 점검기는 사람이 부르는 것이라 느려도 된다. 조회까지 다 해 본다.
    qmd_path, qmd_how = paths.qmd()
    if qmd_path:
        rows.append(_row("qmd", "{}  ({})".format(qmd_path, qmd_how), True))
        rows.append(_row("쓰는 검색기", "qmd 의미검색", True))
    else:
        rows.append(_row(
            "qmd", qmd_how, False,
            "없어도 돈다. 의미검색을 쓰려면 `npm i -g @tobilu/qmd`."))
        rows.append(_row("쓰는 검색기", "기본 검색기 (글자 겹침, 의존 없음)", True))

    cfg = paths.config_file()
    if not cfg:
        rows.append(_row(
            "설정 파일", "(아직 없다 — 관례 위치에도 없음)", True))
    elif os.path.isfile(cfg):
        rows.append(_row("설정 파일", cfg, True))
    else:
        rows.append(_row("설정 파일", cfg + "  (아직 없음)", True))

    rows.append(_row("node", paths.NODE,
                     os.path.exists(paths.NODE) or paths.NODE == "node"))

    if os.path.exists(paths.INDEX) or os.path.exists(paths.INDEX + "-wal"):
        rows.append(_row("검색 색인", paths.INDEX, True))
    else:
        rows.append(_row(
            "검색 색인", paths.INDEX, False,
            "아직 없다. qmd 를 쓸 거라면 `qmd update && qmd embed` 를 한 번 돌린다."))

    # 설정값은 값만 찍지 않고 **어디서 왔는지**를 같이 찍는다. 안 먹는 설정을
    # 고쳐 놓고 먹는 줄 아는 것이 이 플러그인에서 제일 흔한 사고다.
    for key, default, env, cast in (
            ("index_group", "검증·판단 방법론", None, None),
            ("min_score", 0.35, None, float),
            ("builtin_min_score", 0.12, None, float),
            ("max_hits", 3, None, float)):
        val, src = paths.option_with_source(key, default, env, cast)
        rows.append(_row("  " + key, "{}   ({})".format(val, src), True))

    val, src = paths.qmd_timeout_with_source()
    rows.append(_row("  qmd_timeout", "{:g}초   ({})".format(val, src), True))

    # 매니페스트 둘이 갈렸는지. 갈리면 한쪽 제품에서만 낡은 것이 돈다.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import manifests
        bad = manifests.compare(manifests._read(manifests.CLAUDE),
                                manifests._read(manifests.CODEX))
        rows.append(_row("매니페스트 둘", "일치" if not bad else "; ".join(bad),
                         not bad,
                         "python hooks/manifests.py 로 확인한다."))
    except Exception as e:
        rows.append(_row("매니페스트 둘", "확인 못 함 — {}".format(e), False,
                         "매니페스트 파일 둘이 다 있는지 본다."))

    return rows


def main():
    rows = collect()
    width = max(_width(r[0]) for r in rows)
    bad = 0
    for label, value, ok, hint in rows:
        print("{}  {}  {}".format(
            "OK     " if ok else "MISSING", _pad(label, width), value))
        if not ok:
            bad += 1
            if hint:
                print("{}  {}  → {}".format(" " * 7, " " * width, hint))

    print()
    if bad:
        print("{}건이 아직 설정되지 않았다.".format(bad))
    else:
        print("전부 설정됐다.")
    return 0   # 점검기는 판정을 보고할 뿐 실패로 끝나지 않는다


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        sys.exit(main())
    except Exception as e:
        print("점검기 자체가 실패했다 — {}".format(e))
        sys.exit(0)
