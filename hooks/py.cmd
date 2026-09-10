@echo off
rem 훅용 파이썬 실행기 (Windows). hooks/py.sh 의 짝이다.
rem
rem 사용: py.cmd [--quiet] <스크립트.py>
rem
rem 파이썬이 없으면 한 줄을 내고 종료코드 0 으로 끝난다. 작업은 막지 않되
rem 침묵하지 않는다. py.sh 와 같은 규칙이다.
rem
rem 주의: 이 파일은 macOS 에서 작성했고 Windows 에서 실측하지 않았다.
rem       docs/platforms.md 에 그렇게 적어 두었다.
setlocal
chcp 65001 >nul 2>&1
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
