@echo off
rem 훅용 파이썬 실행기 (Windows). hooks/py.sh 의 짝이다.
rem
rem 사용: py.cmd [--quiet] <스크립트.py>
rem
rem 파이썬이 없으면 한 줄을 내고 종료코드 0 으로 끝난다. 작업은 막지 않되
rem 침묵하지 않는다. py.sh 와 같은 규칙이다.
rem
rem 줄바꿈은 CRLF 여야 한다. LF 로 두면 cmd 가 한글 주석을 명령으로 읽는다.
rem chcp 는 표준 입력을 먹는다. <nul 을 빼면 훅 입력이 파이썬에 0 바이트로 간다.
rem (둘 다 2026-09-23 Windows 11 실측)
setlocal
chcp 65001 <nul >nul 2>&1
set "DIR=%~dp0"
set "QUIET=0"
set "SCRIPT=%~1"
if /I "%~1"=="--quiet" (
  set "QUIET=1"
  set "SCRIPT=%~2"
)

set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :run
where python3 >nul 2>&1
if not errorlevel 1 set "PY=python3"
if defined PY goto :run
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :run

if "%QUIET%"=="0" (
  echo claude-lessons-loop: 파이썬 3 을 못 찾아 교훈 회수가 통째로 꺼져 있다.
  echo   확인: python --version
  echo   없으면 설치하거나, 있는데 못 찾는 것이면 PATH 를 확인한다.
)
exit /b 0

:run
set "PYTHONIOENCODING=utf-8"
%PY% "%DIR%%SCRIPT%"
exit /b 0
