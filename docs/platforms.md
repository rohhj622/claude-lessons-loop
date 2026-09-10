# 어디까지 실제로 돌려 봤나

이 파일의 규칙은 하나다. **안 재본 칸은 비워 두지 않고 "안 재봤다"고 적는다.**
빈칸은 통과로 읽힌다.

측정은 `sh hooks/py.sh doctor.py` 와 훅 넷을 실제로 돌려서 한다.
추측으로 채우지 않는다. 새 조합에서 돌려 본 사람은 줄을 채우고 날짜를 적는다.

---

## 조합별 상태

| 조합 | 상태 | 마지막 실측 |
|---|---|---|
| macOS 26.6 · Apple Silicon · Homebrew node | 훅 넷 전부 확인 | 2026-09-10 |
| Windows 11 · Git Bash | 안 재봤다 (아래 주의) | — |
| Windows 11 · WSL | 안 재봤다 (아래 주의) | — |
| macOS · Intel | 안 재봤다 | — |
| Linux | 안 재봤다 | — |

---

## macOS 26.6 · Apple Silicon (2026-09-10)

Claude Code 2.1.267 · Node v24.20.0 · npm 11.19.0 · Python 3.13.11 · qmd 2.8.3.
node 는 Homebrew(`/opt/homebrew/opt/node@24/bin/node`).

확인한 것.

- 훅 넷이 실제 세션에서 돈다. `claude -p --plugin-dir .` 로 띄워 모델에게 자기
  컨텍스트를 옮겨 적게 해서 확인했다. 세션 시작 훅의 상시 교훈과 발화 훅의
  회수 블록이 둘 다 나왔다.
- 미설정 상태에서 훅 넷이 전부 조용히 통과하고 exit 0 으로 끝난다.
- 기본 검색기와 qmd 양쪽으로 회수가 붙는다.

### 회수 왕복 실측

| 검색기 | 시간 |
|---|---|
| 기본 검색기 | 0.02초 |
| qmd 웜 | 1.3초 · 4.6초 |
| qmd 콜드(첫 질의) | 55.6초 |

**qmd 콜드 한 번은 훅 제한 15초를 한참 넘긴다.** 그 발화는 교훈 없이 넘어가고,
지금은 기본 검색기가 대신 받아 이유를 같이 낸다. README 가 적어 둔 Windows
콜드 7.9~8.7초와 크게 다르다. 기계마다 다르다고 보는 편이 맞다.

### 걸렸던 것

- **Homebrew 의 전역 npm 위치가 `/opt/homebrew/lib/node_modules` 다.**
  초판의 `paths.py` 후보 목록에 없어서 qmd 를 못 찾았고, 회수와 재색인이
  통째로 조용히 죽어 있었다. 지금은 나열식 후보에 넣었고, 그것도 새면
  `npm root -g` 로 물어본다.
- `~/.nvm/versions/node/current` 는 nvm 이 기본으로 만드는 심볼릭 링크가 아니다.
- BSD sed 는 GNU 확장 `\L` 을 모른다. `C:/Users/x` 를 `/mnt/LC/Users/x` 로
  만든다. 지금은 `tr` 로 바꿨다.
- 이 기계의 npm 이 install-scripts 를 막아 둬서 `node-llama-cpp` 의 postinstall
  이 안 돌았다. **그래도 임베딩과 질의는 정상이었다.**
- qmd 2.8.3 의 기본 임베딩 모델은 `embeddinggemma-300M` 이다.

---

## Windows · WSL 주의

초판은 Windows 11 에서 만들었고 Git Bash 와 WSL 양쪽에서 돌았다고 되어 있다.
다만 **그 실측 이후에 바꾼 것이 많아 회귀를 확인하지 못했다.** 그 기계에
접근할 수 있을 때 아래를 다시 봐야 한다.

- 훅 명령을 exec 형식(`command` 문자열 + `args` 배열)으로 바꿨다. 초판의 배열
  형식은 무효였고 훅이 통째로 무시되고 있었다. Git Bash 에서 `sh` 가 PATH 에
  잡히는지 확인이 필요하다.
- `session-start.sh` 를 지우고 `session-start.py` 로 옮겼다. **파이썬이 없는
  환경에서는 상시 교훈도 같이 꺼진다.** 전에는 셸이라 살았다. 의도한 맞바꿈이다.
- WSL 경로 변환의 `sed` 를 고쳤다. `C:/x` → `/mnt/c/x` 가 맥에서 나오는 것은
  확인했지만, 실제 WSL 에서 그 경로가 잡히는지는 못 봤다.
- `npm root -g` 가 Git Bash 와 PowerShell 에서 같은 값을 주는지 확인 안 했다.

---

## 알려진 의존

- 훅 넷 다 **파이썬 3** 이 필요하다. 없으면 `py.sh` 가 조용히 통과한다.
- **qmd 는 선택이다.** 없으면 기본 검색기가 받는다. 의존이 없고 0.02초다.
- `_Meta/drift.py` 만 **PyYAML** 이 필요하다. 없으면 그렇게 말하고 exit 0 한다.
  이 맥의 시스템 파이썬에는 없어서 가상환경으로 확인했다.
