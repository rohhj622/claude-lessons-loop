#!/usr/bin/env python3
"""볼트 드리프트 보고서 — 적어 둔 것과 실제가 어긋난 자리를 찾아 보고한다.

막지 않는다. 종료코드는 항상 0 이고, 고칠지는 사람이 정한다.
검사 넷:
  1. 끊긴 [[링크]]        — 노트·별칭·ISS/PRJ ID 접두·_PRJ 언더스코어 어느 것으로도 안 풀리는 대상
  2. 없는 볼트 파일 경로   — `폴더/파일.md` 꼴 문자열 중 볼트 안 경로인데 파일이 없는 것
  3. 손으로 쓴 총계        — 규범 문서(CLAUDE.md·_Meta·Runbooks·People)의 "N곳 중 M곳"류
  4. 표제어 후보           — 1 중 Glossary 에 올릴 만한 이름(자리표시자·첨부·저장소명 제외)
  5. 중복 ID              — 같은 `id` 를 든 노트가 둘 이상. ID 는 볼트 전역에서 고유해야 한다

시작할 때 일부러 깨진 표본으로 검사기 자신을 먼저 확인한다(양성 대조).
사용: python _Meta/drift.py [--json] [--vault 경로]
"""
import io, os, re, sys, json, collections

try:
    import yaml
except ImportError:  # yaml 이 없으면 프론트매터를 못 읽는다 — 조용히 넘어가지 않는다
    print("PyYAML 이 없다. pip install pyyaml", file=sys.stderr)
    sys.exit(0)

SKIP_DIRS = {'.git', '.claude', '.obsidian', '.trash', 'node_modules'}
HISTORY_DIRS = ('Daily/',)            # 이력 동결. 검사 대상에서 뺀다
TEMPLATE_DIRS = ('Templates/',)       # Templater 구문이 링크처럼 보인다
EXAMPLE_FILES = ('_Meta/ontology.md', '_Meta/schema.md', 'CLAUDE.md')
# 위 셋의 링크는 규격을 보여 주는 예시라 실재하지 않아도 결함이 아니다(MySQL DB A·하네스 A 등).
NORMATIVE = ('CLAUDE.md', '_Meta/', 'Runbooks/', 'People/')   # 검사 3 대상
# 볼트 안 경로로 볼 최상위 폴더. Lessons/ 와 _Meta/ 만 이 플러그인이 만들고
# 나머지는 같이 쓰는 사람의 폴더다. 없으면 그냥 안 걸린다.
VAULT_TOP = ('_Meta/', 'Lessons/', 'Projects/', 'People/', 'Runbooks/', 'Templates/',
             'Components/', 'Technologies/', 'Organizations/', 'Glossary/', 'Daily/', '_Attachments/')
# 'Claude' 는 스키마가 시키는 표기다 — 노트를 에이전트가 썼으면 author 에
# "[[Claude]]" 를 넣으라고 되어 있다. 그 이름의 노트를 따로 두라는 뜻이 아니다.
# 갓 만든 볼트가 첫날부터 잡음을 내면 사람이 이 도구를 통째로 무시하게 된다.
PLACEHOLDERS = {'이름', '링크', '노트명', '위키링크', 'LSN-...', 'Lessons', 'Projects', 'prj', 'PRJ-XXXX',
                'ISS-XXXX', '상위 조직', '담당자', '작성자', 'Claude'}

# 자리표시자가 박힌 경로는 실재하지 않는 것이 정상이다. 스키마 문서가 파일 이름
# 규격을 보여 줄 때 쓴다.
PLACEHOLDER_PATH = re.compile(r'YYYY|MM-DD|NNN|XXXX|<[^>]+>')
TOTAL_PATTERNS = [
    re.compile(r'\d+\s*곳\s*중\s*\d+\s*곳'),
    re.compile(r'\d+\s*/\s*\d+\s*(배치|건|곳)'),
    re.compile(r'\d+\s*건\s*중\s*\d+\s*건'),
    re.compile(r'나머지\s*\d+\s*곳'),
]
LINK_RE = re.compile(r'!?\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|[^\]]*)?\]\]')
PATH_RE = re.compile(r'`([^`\n]+?\.md)`')
CODE_RE = re.compile(r'```.*?```', re.S)
INLINE_RE = re.compile(r'``.+?``|`[^`\n]+`')  # 백틱 안의 [[링크]] 는 예시 문자열이지 링크가 아니다. ``이중 백틱``도 받는다
DELETED_RE = re.compile(r'지웠|지운|삭제|폐지|없앴|제거')  # 삭제 사실을 적은 서술은 결함이 아니다


def find_vault(start):
    """볼트 루트를 위로 올라가며 찾는다.

    전에는 루트에 CLAUDE.md 가 있어야 한다고 봤다. 교훈만 쓰는 볼트에는 그 파일이
    없어서 못 찾았고, 그 상태로 자가검사가 '있는 노트(CLAUDE)가 안 풀린다' 를
    내며 검사기가 통째로 멈췄다. 볼트를 볼트이게 하는 것은 _Meta/ 와 Lessons/ 다.
    """
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, '_Meta')) and (
                os.path.isdir(os.path.join(d, 'Lessons'))
                or os.path.isfile(os.path.join(d, 'CLAUDE.md'))):
            return d
        p = os.path.dirname(d)
        if p == d:
            return os.path.abspath(start)
        d = p


class Vault:
    def __init__(self, root):
        self.root = root
        self.files = set()                          # 볼트 상대경로 전부(md 외 포함)
        self.notes = {}                             # 상대경로 -> {'fm':..., 'body':...}
        self.basenames = collections.defaultdict(list)
        self.aliases = collections.defaultdict(list)
        self.idmap = collections.defaultdict(list)
        self.repo_names = set()
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for f in fn:
                rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, '/')
                self.files.add(rel)
                self.basenames[f].append(rel)
                if f.endswith('.md'):
                    self.basenames[f[:-3]].append(rel)
                    self._load(rel)

    def _load(self, rel):
        t = io.open(os.path.join(self.root, rel), encoding='utf-8', errors='replace').read()
        fm = {}
        if t.startswith('---'):
            end = t.find('\n---', 3)
            if end > 0:
                try:
                    fm = yaml.safe_load(t[3:end]) or {}
                    if not isinstance(fm, dict):
                        fm = {}
                except Exception:
                    fm = {}
        self.notes[rel] = {'fm': fm, 'body': t}
        a = fm.get('aliases')
        if a:
            for x in (a if isinstance(a, list) else [a]):
                self.aliases[str(x)].append(rel)
        b = os.path.basename(rel)[:-3]
        m = re.match(r'^_?(ISS-\d{3}-\d{4}-\d{2}-\d{2}-\d{3}'
                     r'|(?:ISS|LSN)-\d{4}-\d{2}-\d{2}-\d{3}'
                     r'|PRJ-\d{4}-\d{3}|CMP-\d{3})', b)
        if m:
            self.idmap[m.group(1)].append(rel)
        if b.startswith('_'):
            self.idmap[b[1:]].append(rel)
        r = fm.get('repo')
        if fm.get('type') == 'project' and r:
            for x in (r if isinstance(r, list) else [r]):
                self.repo_names.add(re.sub(r'^\[\[|\]\]$', '', str(x).strip()))

    def resolve(self, target):
        t = target.strip()
        if not t:
            return True
        b = t.split('/')[-1]
        for k in (t, b):
            if k in self.basenames or k + '.md' in self.basenames or k in self.files:
                return True
            if k in self.aliases or k in self.idmap:
                return True
        return False

    def is_placeholder(self, t):
        return (t in PLACEHOLDERS or '<%' in t or '"' in t or t.startswith('$')
                or t.startswith('<') or t.endswith('>'))


def check_links(v):
    """검사 1·4. {대상: [출처...]} 와 후보 집합을 돌려준다."""
    broken = collections.defaultdict(list)
    for rel, n in v.notes.items():
        if rel.startswith(HISTORY_DIRS + TEMPLATE_DIRS):
            continue
        if rel in EXAMPLE_FILES:
            continue                       # 규격 예시용 링크다
        body = INLINE_RE.sub('', CODE_RE.sub('', n['body']))
        for m in LINK_RE.finditer(body):
            t = m.group(1).strip()
            if v.is_placeholder(t) or v.resolve(t):
                continue
            broken[t].append(rel)
    candidates = {t for t in broken
                  if t not in v.repo_names
                  and not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf|py|csv|excalidraw)$', t, re.I)
                  and not t.startswith(('ISS-', 'LSN-', 'PRJ-', 'CMP-'))
                  and not re.search(r'-20\d\d-\d\d', t)       # 사건·날짜가 박힌 이름은 표제어가 아니다
                  and not all(s.startswith('Lessons/') for s in broken[t])}   # 교훈 본문의 일회성 언급
    return broken, candidates


def check_paths(v):
    """검사 2. 볼트 안 경로로 보이는 `x.md` 문자열 중 없는 것."""
    missing = collections.defaultdict(list)
    for rel, n in v.notes.items():
        if rel.startswith(HISTORY_DIRS):
            continue
        for m in PATH_RE.finditer(n['body']):
            p = m.group(1).strip().replace('\\', '/')
            if '*' in p or '<' in p or '{' in p or ':' in p or p.startswith(('~', '/', '@')):
                continue
            if PLACEHOLDER_PATH.search(p):
                continue        # 규격을 보여 주는 자리표시자다
            if not (p.startswith(VAULT_TOP) or p in ('CLAUDE.md',)):
                continue                       # 코드 저장소 경로다
            if p in v.files:
                continue
            line = n['body'][max(0, m.start() - 120):m.end() + 120]
            if DELETED_RE.search(line):
                continue        # "지웠다"는 서술이다. 끊긴 참조가 아니다
            missing[p].append(rel)
    return missing


def check_totals(v):
    """검사 3. 규범 문서의 손으로 쓴 총계."""
    hits = []
    for rel, n in v.notes.items():
        if not rel.startswith(NORMATIVE):
            continue
        for i, line in enumerate(n['body'].splitlines(), 1):
            for pat in TOTAL_PATTERNS:
                m = pat.search(line)
                if m:
                    hits.append((rel, i, m.group(0), line.strip()[:100]))
                    break
    return hits


class _FakeVault:
    def __init__(self, idmap):
        self.notes = {k: {'fm': {'id': v}} for k, v in idmap.items()}


def check_dup_ids(v):
    """검사 5. 같은 `id` 를 든 노트가 둘 이상이면 낸다. ID 는 볼트 전역에서 고유해야 한다."""
    byid = collections.defaultdict(list)
    for rel, n in v.notes.items():
        i = n['fm'].get('id')
        if i:
            byid[str(i)].append((rel, str(n['fm'].get('project') or '')))
    return {k: sorted(vv) for k, vv in byid.items() if len(vv) > 1}


def self_test(v):
    """양성 대조. 검사기가 깨진 것을 정말 잡는지 먼저 본다."""
    ok = True
    if v.resolve('__이런_노트는_없다__'):
        ok = False; print('자가검사 실패: 없는 노트가 풀린다')
    # 볼트에 반드시 있는 것으로 대조한다. 전에는 CLAUDE 로 쟀는데 교훈만 쓰는
    # 볼트에는 그 노트가 없어서, 멀쩡한 볼트에서 검사기가 자기를 고장났다고 했다.
    anchor = next((os.path.basename(r)[:-3] for r in sorted(v.notes)), '')
    if not anchor:
        ok = False; print('자가검사 실패: 볼트에서 .md 를 한 건도 못 읽었다')
    elif not v.resolve(anchor):
        ok = False; print('자가검사 실패: 있는 노트(%s)가 안 풀린다' % anchor)
    if not any(p.search('배치는 34곳 중 30곳이다') for p in TOTAL_PATTERNS):
        ok = False; print('자가검사 실패: 총계 패턴이 표본을 못 잡는다')
    if '_Meta/__없는파일__.md' in v.files:
        ok = False; print('자가검사 실패: 없는 경로가 있다고 나온다')
    if INLINE_RE.sub('', '`[[예시]]` ``[[이중]]`` 와 [[진짜]]').count('[[') != 1:
        ok = False; print('자가검사 실패: 인라인 코드 제거가 표본과 안 맞는다')
    if not DELETED_RE.search('그 파일은 2026-09-02에 지웠다'):
        ok = False; print('자가검사 실패: 삭제 서술 패턴이 표본을 못 잡는다')
    if not check_dup_ids(_FakeVault({'a.md': 'X', 'b.md': 'X'})):
        ok = False; print('자가검사 실패: 중복 ID 판정이 표본을 못 잡는다')
    if check_dup_ids(_FakeVault({'a.md': 'X', 'b.md': 'Y'})):
        ok = False; print('자가검사 실패: 안 겹치는 ID 를 중복이라 한다')
    return ok


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    root = find_vault(args[args.index('--vault') + 1] if '--vault' in args else os.getcwd())
    v = Vault(root)
    if not self_test(v):
        print('검사기 자체가 깨졌다. 결과를 믿지 말 것.')
        sys.exit(0)
    broken, cand = check_links(v)
    missing = check_paths(v)
    totals = check_totals(v)
    dups = check_dup_ids(v)
    glossary_missing = sorted(c for c in cand if not v.resolve(c))
    if as_json:
        print(json.dumps({'broken_links': broken, 'candidates': glossary_missing,
                          'missing_paths': missing, 'totals': totals, 'dup_ids': dups},
                         ensure_ascii=False, indent=1))
        return
    print(f'볼트: {root}  (노트 {len(v.notes)}건)  자가검사 OK')
    print(f'\n[1] 끊긴 [[링크]] {len(broken)}종 / {sum(len(s) for s in broken.values())}곳')
    for t, srcs in sorted(broken.items(), key=lambda x: -len(x[1])):
        print(f'   [[{t}]] x{len(srcs)}  <- ' + '; '.join(sorted(set(srcs))[:3]))
    print(f'\n[2] 없는 볼트 파일 경로 {len(missing)}종')
    for p, srcs in sorted(missing.items()):
        print(f'   `{p}`  <- ' + '; '.join(sorted(set(srcs))[:3]))
    print(f'\n[3] 규범 문서의 손으로 쓴 총계 {len(totals)}곳')
    for rel, i, hit, line in totals:
        print(f'   {rel}:{i}  "{hit}"  | {line}')
    print(f'\n[4] Glossary 표제어 후보 {len(glossary_missing)}건 (python _Meta/glossary_seed.py 로 심는다)')
    print('   ' + ', '.join(glossary_missing))
    print(f'\n[5] 중복 ID {len(dups)}종 / {sum(len(x) for x in dups.values())}건')
    for i, owners in sorted(dups.items()):
        print(f'   {i}  x{len(owners)}')
        for rel, prj in owners:
            print(f'      {prj:<14} {rel}')


if __name__ == '__main__':
    main()
