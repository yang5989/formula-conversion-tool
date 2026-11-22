@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Formula Conversion Tool - Setup

cd /d "%~dp0"

echo ============================================================
echo   Formula Conversion Tool - One-click Setup
echo ============================================================
echo.

REM ============================================================
REM  Step 1: Locate a usable Python 3.12
REM ============================================================
echo [1/5] Looking for Python 3.12...
echo.

set "PYEXE="

REM --- Try py launcher (ships with python.org installer) ---
py -3.12 -c "import sys;assert sys.version_info[:2]==(3,12)" >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=py -3.12"
    echo       Found via py launcher
    goto :have_python
)

REM --- Try python on PATH ---
python -c "import sys;assert sys.version_info[:2]==(3,12)" >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=python"
    echo       Found python on PATH ^(3.12^)
    goto :have_python
)

REM --- Try python3 ---
python3 -c "import sys;assert sys.version_info[:2]==(3,12)" >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=python3"
    echo       Found python3 on PATH ^(3.12^)
    goto :have_python
)

REM --- Try common install locations ---
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "C:\Python312\python.exe"
    "C:\Program Files\Python312\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys;assert sys.version_info[:2]==(3,12)" >nul 2>&1
        if not errorlevel 1 (
            set "PYEXE=%%~P"
            echo       Found at %%~P
            goto :have_python
        )
    )
)

REM --- Not found: try uv (self-contained, no Python needed) ---
echo       Python 3.12 not found. Will download it via uv...
echo.

where uv >nul 2>&1
if not errorlevel 1 goto :use_uv

REM uv not present - download the standalone exe with PowerShell
echo       Downloading uv...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "try{" ^
  "  $u='https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip';" ^
  "  $z=Join-Path $env:TEMP 'uv.zip';" ^
  "  $d=Join-Path $env:TEMP 'uv_extract';" ^
  "  Invoke-WebRequest -Uri $u -OutFile $z -UseBasicParsing;" ^
  "  if(Test-Path $d){Remove-Item $d -Recurse -Force};" ^
  "  Expand-Archive -Path $z -DestinationPath $d -Force;" ^
  "  $exe=Get-ChildItem $d -Recurse -Filter uv.exe | Select-Object -First 1;" ^
  "  if($exe){Copy-Item $exe.FullName (Join-Path $d 'uv.exe') -Force; Write-Host ('UV_PATH='+$exe.FullName)}" ^
  "}catch{Write-Host 'UV_FAILED'}"

if not exist "%TEMP%\uv_extract\uv.exe" (
    echo.
    echo ============================================================
    echo   [ERROR] Auto-install failed
    echo ============================================================
    echo.
    echo   Please install Python 3.12 manually:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: check "Add python.exe to PATH" during setup
    echo   Then run this script again.
    echo.
    echo ============================================================
    pause
    exit /b 1
)

set "PATH=%TEMP%\uv_extract;%PATH%"
echo       uv downloaded

:use_uv
uv python install 3.12
if errorlevel 1 (
    echo   [ERROR] Failed to download Python 3.12 via uv
    pause
    exit /b 1
)
echo       Python 3.12 installed via uv
set "USE_UV_VENV=1"
goto :make_venv

:have_python
echo.

REM ============================================================
REM  Step 2: Create virtual environment
REM ============================================================
echo [2/5] Creating virtual environment...

if exist ".venv\Scripts\python.exe" (
    echo       .venv already exists, skipping
    goto :install_deps
)

%PYEXE% -m venv .venv
if errorlevel 1 (
    echo   [ERROR] venv creation failed
    pause
    exit /b 1
)
echo       Done

if defined USE_UV_VENV (
    echo.
    echo [2b/5] Rebuilding venv with uv ^(faster^)...
    rmdir /s /q .venv 2>nul
    uv venv --python 3.12 .venv
    if errorlevel 1 (
        echo   [ERROR] venv creation failed
        pause
        exit /b 1
    )
)
goto :install_deps

:make_venv
echo [2/5] Creating virtual environment with uv...
uv venv --python 3.12 .venv
if errorlevel 1 (
    echo   [ERROR] venv creation failed
    pause
    exit /b 1
)
echo       Done

REM ============================================================
REM  Step 3: Install dependencies
REM ============================================================
:install_deps
echo.
echo [3/5] Installing dependencies ^(~2 GB, 5-15 min^)...
echo       Grab a coffee. This takes a while.
echo.

set "PY=.venv\Scripts\python.exe"

REM Prefer uv (10x faster), fall back to pip
uv pip install --python "%PY%" -r requirements.txt 2>nul
if not errorlevel 1 goto :verify

echo       uv failed or unavailable, using pip ^(slower^)...
"%PY%" -m pip install --upgrade pip -q 2>nul
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   [ERROR] Dependency install failed
    echo ============================================================
    echo.
    echo   Common causes:
    echo     1. Network issue - try a mirror:
    echo        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    echo     2. Python is not 3.12
    echo.
    echo ============================================================
    pause
    exit /b 1
)

REM ============================================================
REM  Step 4: Verify
REM ============================================================
:verify
echo.
echo [4/5] Verifying installation...
echo.

"%PY%" -c "import sys;v=sys.version_info;print('  Python: %d.%d.%d'%(v.major,v.minor,v.micro));sys.exit(0 if v[:2]==(3,12) else 1)"
if errorlevel 1 (
    echo   [ERROR] Wrong Python version - need 3.12
    pause
    exit /b 1
)

"%PY%" -c "import importlib.metadata as m;print('  pix2text:',m.version('pix2text'))" 2>nul
"%PY%" -c "import importlib.metadata as m;print('  rapidocr:',m.version('rapidocr'))" 2>nul

"%PY%" -c "import pix2text,rapidocr,PySide6,latex2mathml,win32clipboard" 2>nul
if errorlevel 1 (
    echo.
    echo   [ERROR] Some dependencies failed to import
    echo   Run this to see the error:
    echo     .venv\Scripts\python.exe -c "import pix2text"
    pause
    exit /b 1
)

"%PY%" -c "import rapidocr;v=rapidocr.__version__;raise SystemExit(0 if v.startswith('3.9') else 1)"
if errorlevel 1 (
    echo.
    echo   [WARNING] rapidocr version mismatch ^(need 3.9.2^)
    echo   Fixing...
    "%PY%" -m pip install "rapidocr==3.9.2" -q
)

echo       All checks passed

REM ============================================================
REM  Step 5: Create launchers
REM ============================================================
echo.
echo [5/5] Creating launchers...

call :write_launcher "启动.bat" ""
call :write_launcher "启动(调试模式).bat" "-c"

echo       Done

echo.
echo ============================================================
echo   Setup complete
echo ============================================================
echo.
echo   How to start:
echo     1. Double-click  "启动.bat"        (no console window)
echo     2. Or run         "启动(调试模式).bat"  (shows errors)
echo.
echo   First launch downloads model weights (~400 MB),
echo   takes 1-3 minutes. Later launches take ~12 seconds.
echo.
echo ============================================================
echo.

set /p RUNNOW="Start now? (Y/n): "
if /i not "!RUNNOW!"=="n" (
    start "" ".venv\Scripts\pythonw.exe" -W ignore run.py
)

endlocal
exit /b 0

REM ============================================================
REM  Helper: write a launcher bat
REM  %1 = filename   %2 = "" for normal, "-c" for debug (console)
REM ============================================================
:write_launcher
set "FNAME=%~1"
set "DEBUG=%~2"

if "%DEBUG%"=="" (
    > "%FNAME%" echo @echo off
    >> "%FNAME%" echo cd /d "%%~dp0"
    >> "%FNAME%" echo start "" ".venv\Scripts\pythonw.exe" -W ignore run.py
) else (
    > "%FNAME%" echo @echo off
    >> "%FNAME%" echo chcp 65001 ^>nul
    >> "%FNAME%" echo cd /d "%%~dp0"
    >> "%FNAME%" echo echo Starting in DEBUG mode ^(console visible^)...
    >> "%FNAME%" echo echo.
    >> "%FNAME%" echo ".venv\Scripts\python.exe" -W ignore run.py
    >> "%FNAME%" echo.
    >> "%FNAME%" echo echo === Program exited ===
    >> "%FNAME%" echo pause
)
exit /b 0
