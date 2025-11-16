@echo off
REM Week 7 - PostgreSQL Sink Deployment and Testing

echo ========================================
echo Week 7: PostgreSQL JDBC Sink Deployment
echo ========================================
echo.

REM Step 1: Build
echo Step 1: Building Maven project...
cd src\flink_jobs
call mvn clean package -DskipTests -q
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Maven build failed!
    cd ..\..
    pause
    exit /b 1
)
cd ..\..
echo [SUCCESS] JAR built
echo.

REM Step 2: Cancel old jobs
echo Step 2: Cancelling old jobs...
for /f "tokens=4" %%i in ('docker exec flink-jobmanager flink list ^| findstr "RUNNING"') do (
    docker exec flink-jobmanager flink cancel %%i >nul 2>&1
)
timeout /t 3 /nobreak >nul
echo [SUCCESS] Old jobs cancelled
echo.

REM Step 3: Deploy
echo Step 3: Deploying to Flink...
docker cp src\flink_jobs\target\crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/ >nul 2>&1
echo [SUCCESS] JAR copied
echo.

REM Step 4: Submit
echo Step 4: Submitting job...
docker exec flink-jobmanager flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar
timeout /t 3 /nobreak >nul
echo [SUCCESS] Job submitted
echo.

REM Step 5: Verify
echo Step 5: Verifying job...
docker exec flink-jobmanager flink list | findstr "PostgreSQL"
echo.

echo ========================================
echo Deployment Complete!
echo ========================================
echo.
echo Next Steps:
echo 1. Start producer: START_PRODUCER.bat
echo 2. Wait 2-3 minutes for windows to accumulate
echo 3. Query PostgreSQL:
echo.
echo    docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
echo.
echo 4. View recent data:
echo.
echo    docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT c.symbol, window_start, open_price, close_price FROM price_aggregates_1m p JOIN cryptocurrencies c ON p.crypto_id = c.id ORDER BY window_start DESC LIMIT 5;"
echo.
echo Expected:
echo - Row count increases every ~70 seconds
echo - Both BTC and ETH candles appear
echo - OHLC values match Flink console output
echo.
pause
