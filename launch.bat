@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

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

:: Check for interrupt (Ctrl+C) — continue

:: --- Python check ---
set PYTHON=
where python 2>nul >nul
if !errorlevel! equ 0 (
    python --version 2>&1 | findstr /R "3\.[0-9][0-9]\?\.\|3\.1[0-9]" >nul
    if !errorlevel! equ 0 set PYTHON=python
)

if not defined PYTHON (
    where py 2>nul >nul
    if !errorlevel! equ 0 (
        py --version 2>&1 | findstr /R "3\.[0-9][0-9]\?\.\|3\.1[0-9]" >nul
        if !errorlevel! equ 0 set PYTHON=py
    )
)

if not defined PYTHON (
    call :warn "Python 3.8+ not found."
    call :confirm "Download and install Python 3 from python.org?"
    if !errorlevel! equ 0 (
        echo [INFO] Opening python.org in browser...
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
    call :confirm "Download and install Java 21 (Adoptium) from adoptium.net?"
    if !errorlevel! equ 0 (
        echo [INFO] Opening Adoptium download page...
        start https://adoptium.net/temurin/releases/?version=21
        echo [INFO] After installing, re-run this script.
        pause
        exit /b 0
    ) else (
        call :warn "Continuing without Java — server processes will not start."
    )
) else (
    java -version 2>&1 | findstr "version" >nul
    for /f "tokens=*" %%v in ('java -version 2^^^>&1 ^| findstr "version"') do call :info %%v
)

:: --- Python venv ---
if not exist ".venv\Scripts\python.exe" (
    call :info "Creating Python virtual environment..."
    "%PYTHON%" -m venv .venv
)

call .venv\Scripts\activate.bat

:: --- Install pip deps ---
call :info "Installing Python dependencies..."
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

call :info "All dependencies installed."

:: --- Autostart setup ---
call :confirm "Add Windfall ECU to startup (Windows Startup folder)?"
if !errorlevel! equ 0 (
    set "STARTUP_LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Windfall ECU.lnk"
    if exist "%STARTUP_LINK%" (
        call :info "Startup shortcut already exists."
    ) else (
        echo [INFO] Creating startup shortcut in:
        echo        "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"
        echo [INFO] To create it manually:
        echo       1. Press Win+R, type: shell:startup
        echo       2. Create a shortcut to: "%SCRIPT_DIR%launch.bat"
        call :confirm "Create a startup shortcut using PowerShell?"
        if !errorlevel! equ 0 (
            powershell -Command ^
                $ws = New-Object -ComObject WScript.Shell; ^
                $s = $ws.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Windfall ECU.lnk'); ^
                $s.TargetPath = '%SCRIPT_DIR%launch.bat'; ^
                $s.WorkingDirectory = '%SCRIPT_DIR%'; ^
                $s.WindowStyle = 7; ^
                $s.Description = 'Windfall ECU — Minecraft Server Manager'; ^
                $s.Save()
            if !errorlevel! equ 0 (
                call :info "Startup shortcut created."
            ) else (
                call :warn "Could not create shortcut. You can create it manually."
            )
        )
    )
)

:: --- Launch ---
echo.
call :info "Starting Windfall ECU on http://localhost:8080"
echo   Default login: admin / admin
echo.
echo Press Ctrl+C to stop the server.
echo.
python app.py
if !errorlevel! neq 0 (
    call :fatal "Windfall ECU exited with an error."
)

pause
