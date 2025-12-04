@echo off
title ANAGHA SOLUTION - Installation
color 0A
echo.
echo ========================================
echo   ANAGHA SOLUTION - Bulk Email Software
echo   Installation Script
echo ========================================
echo.

REM Check Python installation
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python 3.8 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

python --version
echo Python found!
echo.

REM Create virtual environment
echo [2/4] Creating virtual environment...
if exist "venv\" (
    echo Virtual environment already exists.
) else (
    python -m venv venv
    echo Virtual environment created.
)
echo.

REM Activate and install dependencies
echo [3/4] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo Dependencies installed successfully!
echo.

REM Create desktop shortcut (optional)
echo [4/4] Setup complete!
echo.
echo ========================================
echo   Installation Successful!
echo ========================================
echo.
echo To run the application:
echo   1. Double-click run.bat
echo   2. Or run: python main.py
echo.
echo To create executable:
echo   python build_exe.py
echo.
pause

