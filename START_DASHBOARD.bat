@echo off
REM ============================================
REM Streamlit Dashboard Launcher
REM Phase 4 - Week 9
REM ============================================

echo.
echo ======================================
echo   Starting Crypto Market Dashboard
echo ======================================
echo.

REM Change to project root
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then: venv\Scripts\activate
    echo Then: pip install -r requirements.txt -r requirements-dashboard.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if Streamlit is installed
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo.
    echo [WARNING] Streamlit not installed!
    echo [INFO] Installing dashboard dependencies...
    pip install -r requirements-dashboard.txt
)

REM Check if API is running
echo.
echo [INFO] Checking if API is running...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] API is not running!
    echo [INFO] Please start the API first:
    echo   START_API.bat
    echo.
    echo Press any key to continue anyway, or Ctrl+C to exit...
    pause >nul
)

REM Start Streamlit dashboard
echo.
echo [INFO] Starting Streamlit dashboard...
echo [INFO] Dashboard URL: http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard
echo.

streamlit run src\dashboard\app.py --server.port 8501 --server.headless true

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start dashboard
    pause
)
