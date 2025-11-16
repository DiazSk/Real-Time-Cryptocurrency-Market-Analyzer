@echo off
REM Start the cryptocurrency price alert consumer
REM Monitors 'crypto-alerts' Kafka topic for anomaly detection alerts

echo Starting Alert Consumer...
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
    echo.
)

REM Run the alert consumer
python src\consumers\alert_consumer.py

pause
