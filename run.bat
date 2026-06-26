@echo off
setlocal EnableDelayedExpansion

rem ===========================================================================
rem  CorbeauSplat (Windows / CUDA) launcher
rem  Sets up a Python virtual environment, installs dependencies, checks
rem  external engines (COLMAP, Brush, ...) and launches the application.
rem ===========================================================================

cd /d "%~dp0"
echo Working directory: %CD%

rem --- Phase 0: Clean Reset (--clean flag) ---
set "CLEAN_MODE="
set "FILTERED_ARGS="
for %%A in (%*) do (
    if /I "%%~A"=="--clean" (
        set "CLEAN_MODE=1"
    ) else (
        set "FILTERED_ARGS=!FILTERED_ARGS! %%A"
    )
)

if defined CLEAN_MODE (
    echo.
    echo  WARNING: CLEAN MODE
    echo     This will delete:
    echo       - .venv, .venv_360, .venv_4dgs  ^(Python environments^)
    echo       - engines\                       ^(COLMAP, Brush, Glomap binaries^)
    echo       - config.json                    ^(configuration^)
    echo.
    set /p "CONFIRM=    Confirm full reset? (y/n): "
    if /I "!CONFIRM!"=="y" (
        echo Cleaning...
        rmdir /s /q ".venv"      2>nul
        rmdir /s /q ".venv_360"  2>nul
        rmdir /s /q ".venv_4dgs" 2>nul
        rmdir /s /q "engines"    2>nul
        del /q "config.json"     2>nul
        echo Done.
    ) else (
        echo Cancelled. Normal launch.
    )
    echo.
)

rem --- Phase 0.5: Prerequisites ---
echo --- Phase 0.5: Checking prerequisites ---
where git >nul 2>&1 || echo  ^(info^) git not found - updates and source builds will be unavailable.
where nvidia-smi >nul 2>&1 && (echo  NVIDIA GPU detected - CUDA acceleration available.) || (echo  ^(info^) nvidia-smi not found - running on CPU. Install the NVIDIA driver for CUDA.)

rem --- Phase 0.7: Auto-update from git (latest fixes) ---
if exist ".git" (
    where git >nul 2>&1 && (
        echo --- Phase 0.7: Checking for updates ---
        git pull --ff-only 2>nul && (
            echo  Up to date with the latest version.
        ) || (
            echo  ^(info^) Could not fast-forward ^(local changes or offline^) - continuing with current version.
        )
    )
)

rem --- Phase 1: Locate Python ---
echo --- Phase 1: Environment configuration ---
set "VENV_DIR=.venv"
set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_CMD%" (
    echo Creating virtual environment...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"

    set "SELECTED_PY="
    for %%P in (python py python3) do (
        if not defined SELECTED_PY (
            where %%P >nul 2>&1 && set "SELECTED_PY=%%P"
        )
    )
    if not defined SELECTED_PY (
        echo ERROR: Python 3 not found. Install Python 3.11+ from https://www.python.org/downloads/
        exit /b 1
    )
    echo Detected Python launcher: !SELECTED_PY!
    !SELECTED_PY! -m venv "%VENV_DIR%" || (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created.
)

for /f "delims=" %%V in ('"%PYTHON_CMD%" --version') do echo Using environment Python: %%V

rem --- Phase 2: Dependency sync ---
echo --- Phase 2: Synchronizing dependencies ---
"%PYTHON_CMD%" -m pip install --upgrade pip >nul 2>&1

set "DEP_FILE=requirements.txt"
if exist "requirements.lock" set "DEP_FILE=requirements.lock"
echo Using dependency list: %DEP_FILE%

"%PYTHON_CMD%" -m pip install -r "%DEP_FILE%" >nul 2>&1
if errorlevel 1 (
    echo  Silent install failed, retrying with logs...
    "%PYTHON_CMD%" -m pip install -r "%DEP_FILE%"
)

"%PYTHON_CMD%" -c "import PyQt6" >nul 2>&1 || "%PYTHON_CMD%" -m pip install PyQt6
"%PYTHON_CMD%" -c "import plyfile" >nul 2>&1 || "%PYTHON_CMD%" -m pip install plyfile
echo Dependencies synchronized.

rem --- Phase 3: Engine check ---
echo --- Phase 3: Verifying engines and external binaries ---
"%PYTHON_CMD%" -m app.scripts.setup_dependencies --startup
echo System check complete.

rem --- Phase 4: Launch ---
echo --- Phase 4: Launching CorbeauSplat ---
echo ------------------------------------------------
"%PYTHON_CMD%" main.py%FILTERED_ARGS%

endlocal
