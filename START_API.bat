@echo off
REM ============================================
REM FastAPI Backend Launcher
REM Phase 4 - Week 8
REM ============================================

echo.
echo ======================================
echo   Starting Crypto Market Analyzer API
echo ======================================
echo.

REM Change to project root
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then: venv\Scripts\activate
    echo Then: pip install -r requirements.txt -r requirements-api.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if FastAPI dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo.
    echo [WARNING] FastAPI not installed!
    echo [INFO] Installing API dependencies...
    pip install -r requirements-api.txt
)

REM Start FastAPI with uvicorn
echo.
echo [INFO] Starting FastAPI server on http://localhost:8000
echo [INFO] API Documentation: http://localhost:8000/docs
echo [INFO] WebSocket Test: http://localhost:8000/ws/test
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start API server
    pause
)
