@echo off
REM Week 7 - Redis Sink Deployment and Testing

echo ========================================
echo Week 7: Redis Cache Sink Deployment
echo ========================================
echo.

REM Step 1: Build
echo Step 1: Building Maven project with Redis sink...
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
    echo [INFO] Cancelling job: %%i
    docker exec flink-jobmanager flink cancel %%i >nul 2>&1
)
timeout /t 3 /nobreak >nul
echo [SUCCESS] Old jobs cancelled
echo.

REM Step 3: Test Redis connectivity
echo Step 3: Testing Redis connectivity...
docker exec redis redis-cli ping >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Redis is reachable
) else (
    echo [ERROR] Cannot reach Redis container
    pause
    exit /b 1
)
echo.

REM Step 4: Deploy
echo Step 4: Deploying to Flink...
docker cp src\flink_jobs\target\crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/ >nul 2>&1
echo [SUCCESS] JAR copied
echo.

REM Step 5: Submit
echo Step 5: Submitting job with PostgreSQL + Redis sinks...
docker exec flink-jobmanager flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar
timeout /t 3 /nobreak >nul
echo [SUCCESS] Job submitted
echo.

REM Step 6: Verify
echo Step 6: Verifying job...
docker exec flink-jobmanager flink list
echo.

echo ========================================
echo Deployment Complete!
echo ========================================
echo.
echo Next Steps:
echo 1. Start producer: START_PRODUCER.bat
echo 2. Wait 2 minutes for windows
echo 3. Query Redis:
echo.
echo    docker exec redis redis-cli GET crypto:BTC:latest
echo    docker exec redis redis-cli GET crypto:ETH:latest
echo.
echo 4. Verify PostgreSQL still working:
echo.
echo    docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
echo.
echo Expected:
echo - Redis keys exist with JSON data
echo - TTL set to 300 seconds
echo - PostgreSQL still receiving data
echo - Both sinks working in parallel
echo.
pause
