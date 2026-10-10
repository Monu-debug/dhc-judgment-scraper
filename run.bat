@echo off
REM Delhi High Court Income Tax Judgment Scraper - Easy Run Batch File
REM This script sets up the environment and runs the scraper.

REM Change to the script directory
cd /d "%~dp0"

REM Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Check if dependencies are installed, if not install them
REM We'll try to import a key module to see if dependencies are present
python -c "import requests, bs4, flask" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Check if Telegram credentials are set
if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo.
    echo Warning: TELEGRAM_BOT_TOKEN environment variable is not set.
    echo Please set it to your Telegram bot token.
    echo.
    REM We'll still run the script; it will log instead of sending
)

if "%TELEGRAM_CHAT_ID%"=="" (
    echo Warning: TELEGRAM_CHAT_ID environment variable is not set.
    echo Please set it to your Telegram chat ID.
    echo.
)

REM Run the main script
echo.
echo Starting Delhi High Court Income Tax Judgment Scraper...
echo The script will check if it's 4:00 PM IST before running.
echo To get notifications, please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
echo.
python main.py

REM Keep the window open so user can see output
echo.
echo Script execution completed.
pause