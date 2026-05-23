@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:info  echo [INFO]  %*
goto :eof
:warn  echo [WARN]  %*
goto :eof
:fatal echo [FATAL] %* & exit /b 1
:confirm
    set /p ans="[?] %* [y/N] "
    if /i "!ans!"=="y" exit /b 0
    if /i "!ans!"=="yes" exit /b 0
    exit /b 1
goto :eof

:: --- Find Python everywhere ---
set PYTHON=

:: Check common names + version-specific
for %%p in (python313 python312 python311 python310 python39 python38 python3 python) do (
    if not defined PYTHON (
        where %%p 2>nul >nul
        if !errorlevel! equ 0 (
            %%p --version 2>&1 | findstr /R "3\.[0-9][0-9]\?\.\|3\.1[0-9]" >nul
            if !errorlevel! equ 0 set PYTHON=%%p
        )
    )
)

:: Check py launcher
if not defined PYTHON (
    where py 2>nul >nul
    if !errorlevel! equ 0 (
        py --version 2>&1 | findstr /R "3\.[0-9][0-9]\?\.\|3\.1[0-9]" >nul
        if !errorlevel! equ 0 set PYTHON=py
    )
)

:: Check common install paths
if not defined PYTHON (
    for %%d in ("%LOCALAPPDATA%\Programs\Python\Python*" "%ProgramFiles%\Python*") do (
        if exist "%%d\python.exe" (
            "%%d\python.exe" --version 2>&1 | findstr /R "3\.[0-9][0-9]\?\.\|3\.1[0-9]" >nul
            if !errorlevel! equ 0 set PYTHON=%%d\python.exe
        )
    )
)

if not defined PYTHON (
    call :warn "Python 3.8+ not found."
    call :confirm "Download and install Python 3 from python.org?"
    if !errorlevel! equ 0 (
        start https://www.python.org/downloads/
        echo [INFO] After installing, re-run this script.
        pause
        exit /b 0
    ) else (
        call :fatal "Python 3 is required. Aborting."
    )
)

for /f "tokens=*" %%v in ('%PYTHON% --version 2^^^>nul') do call :info %%v

:: --- Java check ---
set JAVA=
where java 2>nul >nul
if !errorlevel! equ 0 (
    java -version 2>&1 | findstr /R "\"1[7-9]\"\|\"2[0-9]\"" >nul
    if !errorlevel! equ 0 set JAVA=java
)
if not defined JAVA (
    call :warn "Java 17+ not found."
    call :confirm "Download and install Java 21 (Adoptium)?"
    if !errorlevel! equ 0 (
        start https://adoptium.net/temurin/releases/?version=21
        echo [INFO] After installing, re-run this script.
        pause
        exit /b 0
    ) else (
        call :warn "Continuing without Java — servers will not start."
    )
) else (
    for /f "tokens=*" %%v in ('java -version 2^^^>&1 ^| findstr "version"') do call :info %%v
)

:: --- Python venv ---
if not exist ".venv\Scripts\python.exe" (
    call :info "Creating virtual environment..."
    "%PYTHON%" -m venv .venv
)
call .venv\Scripts\activate.bat

:: --- Install deps ---
call :info "Installing Python dependencies..."
python -m pip install --upgrade pip -q 2>nul
pip install -r requirements.txt -q 2>nul
call :info "Dependencies ready."

:: --- Build static assets ---
where npm 2>nul >nul
if !errorlevel! equ 0 (
    if not exist "static\js\windfall.min.js" (
        if not exist "node_modules\esbuild" (
            call :info "Installing Node.js dependencies..."
            npm install 2>nul
        )
        if exist "node_modules\esbuild" (
            call :info "Building static assets..."
            npm run build 2>nul
        )
    )
)

:: --- Launch detached ---
echo.
call :info "Starting Windfall ECU on http://localhost:8080"
echo   Default login: admin / admin
echo   Panel running in background. You may close this window.
echo.

:: Start with pythonw (no console) if available, else python in background
set "LOG=%TEMP%\windfall-ecu.log"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.py" > "%LOG%" 2>&1
) else if exist "%PYTHON%\..\pythonw.exe" (
    start "" "%PYTHON%\..\pythonw.exe" "app.py" > "%LOG%" 2>&1
) else (
    start /B "" "%PYTHON%" "app.py" > "%LOG%" 2>&1
)
echo [INFO] Windfall ECU started. Check http://localhost:8080
echo [INFO] Log: %LOG%
